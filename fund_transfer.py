import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from stringprep import b1_set

class fund_transfer(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'fund.transfer'
    _description = "Fund Transfers"
    _columns = {
        'name':fields.char('Transfer ID',size=64,readonly=True),
        'date':fields.date('Transfer Date'),
        'release_date':fields.date('Release Date'),
        'receive_date':fields.date('Receive Date'),
        'type':fields.selection([
                                 ('b2b','Bank to Bank'),
                                 ('a2a','Analytic to Analytic'),
                                 ('p2b','Petty Cash to Bank')
                                 ],'Type'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal', required=True),
        'src_account':fields.many2one('res.partner.bank','Source Bank Account'),
        'pettycash_id':fields.many2one('account.pettycash','Petty Cash Account'),
        'curr_id':fields.many2one('res.currency','Currency'),
        'amount':fields.float('Amount to Transfer'),
        'dest_account':fields.many2one('res.partner.bank','Destination Bank Account'),
        'dest_p2b_account':fields.many2one('res.partner.bank','Destination Bank Account'),
        'src_analytic_account':fields.many2one('account.analytic.account','Source Analytic Account'),
        'dest_analytic_account':fields.many2one('account.analytic.account','Destination Analytic Account'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Releasing Journal Items', readonly=True),
        'b2breleasing_move_id':fields.many2one('account.move','Journal Entry'),
        'b2breleasing_move_ids': fields.related('b2breleasing_move_id','line_id', type='one2many', relation='account.move.line', string='Releasing Journal Items', readonly=True),
        'b2breceiving_move_id':fields.many2one('account.move','Journal Entry'),
        'b2breceiving_move_ids': fields.related('b2breceiving_move_id','line_id', type='one2many', relation='account.move.line', string='Receiving Journal Items', readonly=True),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('requested','Requested'),
                            ('released','Released'),
                            ('done','Transferred'),
                            ('cancel','Cancelled'),
                            ],'State',readonly=True),
        }
    
    _defaults = {
        'period_id':_get_period,
        'state':'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        }
    
    def request(self, cr, uid, ids, context=None):
        for b2b in self.read(cr, uid, ids, context=None):
            name = self.pool.get('ir.sequence').get(cr, uid, 'internal.bank.transfer')
            self.write(cr, uid, ids, {'state':'requested','name':name})
            self.data_get(cr, uid, ids, context)
        return True
    
    def data_get(self, cr, uid, ids, context=None):
        datas = {}
        statements = []
        if context is None:
            context = {}
        for data in self.read(cr, uid, ids, ['id']):
            rec = data['id']
            attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','bank.transfer'),('res_id','=',rec)])
            self.pool.get('ir.attachment').unlink(cr, uid, attachments)
            statements.append(rec)
        datas = {
            'ids':statements,
            'model':'fund.transfer',
            'form':data
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'internal.fund.transfer',
            'nodestroy':True,
            'datas': datas,
            #'name':data['name'],
            'header':False,
            }
    
    def b2b_release(self, cr, uid, ids, context=None):
        for b2b in self.read(cr, uid, ids, context=None):
            b1_read = self.pool.get('res.partner.bank').read(cr, uid, b2b['src_account'][0],context=None)
            b2_read = self.pool.get('res.partner.bank').read(cr, uid, b2b['dest_account'][0],context=None)
            b1_curr = self.pool.get('account.account').read(cr, uid, b1_read['account_id'][0],['company_currency_id','currency_id'])
            currency = False
            rate = False
            journal_id =b2b['journal_id'][0]
            period_id = b2b['period_id'][0]
            date = b2b['release_date']
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            if not b1_curr['currency_id']:
                currency = b1_curr['company_currency_id'][0]
                rate = 1.00
            if b1_curr['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, b1_curr['currency_id'][0],['rate'])
                currency = b1_curr['currency_id'][0]
                rate = curr_read['rate']
            amount = b2b['amount'] / rate
            name = 'Withdrawal from ' + b1_read['acc_number']
            move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':b1_read['account_id'][0],
                    'credit':amount,
                    'date':date,
                    'move_id':move_id,
                    'amount_currency':b2b['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            name = b1_read['transit_id'][1]
            move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':b1_read['transit_id'][0],
                    'debit':amount,
                    'date':date,
                    'move_id':move_id,
                    'amount_currency':b2b['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'b2breleasing_move_id':move_id,'state':'released'})
        return True
    
    def b2b_receive(self, cr, uid, ids, context=None):
        for b2b in self.read(cr, uid, ids, context=None):
            b1_read = self.pool.get('res.partner.bank').read(cr, uid, b2b['src_account'][0],context=None)
            b2_read = self.pool.get('res.partner.bank').read(cr, uid, b2b['dest_account'][0],context=None)
            b1_curr = self.pool.get('account.account').read(cr, uid, b1_read['account_id'][0],['company_currency_id','currency_id'])
            currency = False
            rate = False
            journal_id =b2b['journal_id'][0]
            period_id = b2b['period_id'][0]
            date = b2b['receive_date']
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            if not b1_curr['currency_id']:
                currency = b1_curr['company_currency_id'][0]
                rate = 1.00
            if b1_curr['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, b1_curr['currency_id'][0],['rate'])
                currency = b1_curr['currency_id'][0]
                rate = curr_read['rate']
            amount = b2b['amount'] / rate
            name = 'Deposit to ' + b2_read['acc_number']
            move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':b2_read['account_id'][0],
                    'debit':amount,
                    'date':date,
                    'move_id':move_id,
                    'amount_currency':b2b['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            name = b1_read['transit_id'][1]
            move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':b1_read['transit_id'][0],
                    'credit':amount,
                    'date':date,
                    'move_id':move_id,
                    'amount_currency':b2b['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'b2breceiving_move_id':move_id,'state':'done'})
        return True
    
    def onchange_srcaccount(self, cr, uid, ids, src_account=False):
        result = {}
        if src_account:
            acc_read = self.pool.get('res.partner.bank').read(cr, uid, src_account,['currency_id'])
            result = {'value':{
                        'curr_id':acc_read['currency_id'][0],
                        'dest_account':False,
                          }
                    }
        return result
    
    def onchange_pettycash(self, cr, uid, ids, pettycash_id=False):
        result = {}
        ftp_id = False
        if pettycash_id:
            for p2b in self.read(cr, uid, ids, context=None):
                ftp_id = p2b['id']
                for p2b_denom in p2b['denom_ids']:
                    self.pool.get('pettycash.denom').unlink(cr, uid, p2b_denom)
                ptc_read = self.pool.get('account.pettycash').read(cr, uid, pettycash_id,['currency_id'])
                currency = ptc_read['currency_id'][1]
                denominations = self.pool.get('denominations').search(cr, uid, [('currency_id','=',ptc_read['currency_id'][0])])
                if not denominations:
                    raise osv.except_osv(_('Error!'), _('%s has no available denominations.Please add them!')%currency)
                new_denoms=[]
                if denominations:
                    for denom in denominations:
                        values = {
                            'name':denom,
                            'ft_id':ftp_id,
                            }
                        denom_new= self.pool.get('pettycash.denom').create(cr, uid, values)
                        new_denoms.append(denom_new)
                result = {'value':{
                        'curr_id':ptc_read['currency_id'][0],
                        'denom_ids':new_denoms,
                          }
                    }
        return result
    
    def p2b_transfer(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        result = {}
        for p2b in self.read(cr, uid, ids, context=None):
            amount=False
            for p2b_denom in p2b['denom_ids']:
                denom_check = self.pool.get('pettycash.denom').read(cr, uid, p2b_denom,['name','quantity','amount'])
                if denom_check['quantity'] < 1:
                    continue
                if denom_check['quantity'] > 0:
                    pettycash_name = p2b['pettycash_id'][1]
                    denom_name = denom_check['name'][1]
                    quanti = denom_check['quantity']
                    ptc_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_check['name'][0]),
                                                                                        ('pettycash_id','=',p2b['pettycash_id'][0]),
                                                                                        ('quantity','>=',denom_check['quantity'])])
                    if not ptc_denom_check:
                        raise osv.except_osv(_('Error !'), _('The quantity of %s denomination of pettycash %s is less than the requested quantity to be transferred!')%(denom_name, pettycash_name))
                    if ptc_denom_check:
                        amount +=denom_check['amount']
            self.write(cr, uid, [p2b['id']],{'amount':amount})
            if p2b['dest_p2b_account']:
                ptc_curr = p2b['curr_id'][0]
                check_bank = self.pool.get('res.partner.bank').read(cr, uid, p2b['dest_p2b_account'][0],['account_id'])
                check_acc_curr = self.pool.get('account.account').read(cr, uid, check_bank['account_id'][0],['currency_id','company_currency_id'])
                if check_acc_curr['currency_id']:
                    bank_curr = check_acc_curr['currency_id'][0]
                    if bank_curr !=ptc_curr:
                        raise osv.except_osv(_('Error !'), _('You cannot create a transfer for different currencies!'))
                    if bank_curr ==ptc_curr:
                        self.p2b_entries(cr, uid, ids)
                if not check_acc_curr['currency_id']:
                    bank_curr = check_acc_curr['company_currency_id'][0]
                    if bank_curr !=ptc_curr:
                        raise osv.except_osv(_('Error !'), _('You cannot create a transfer for different currencies!'))
                    if bank_curr == ptc_curr:
                        self.p2b_entries(cr, uid, ids)
            if not p2b['dest_p2b_account']:
                raise osv.except_osv(_('Error !'), _('Please choose a destination account.'))
        return True
    
    def p2b_entries(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        result = {}
        for p2b in self.read(cr, uid, ids, context=None):
            check_bank = self.pool.get('res.partner.bank').read(cr, uid, p2b['dest_p2b_account'][0],['account_id'])
            check_acc_curr = self.pool.get('account.account').read(cr, uid, check_bank['account_id'][0],['currency_id','company_currency_id'])
            if p2b['amount']>0.00:
                amount_currency = False
                currency = False
                amount = 0.00
                if check_acc_curr['company_currency_id'][0]==p2b['curr_id'][0]:
                    amount = p2b['amount']
                    currency = p2b['curr_id'][0]
                    amount_currency = p2b['amount']
                if check_acc_curr['company_currency_id'][0]!=p2b['curr_id'][0]:
                    check_curr = self.pool.get('res.currency').read(cr, uid, p2b['curr_id'][0],['rate'])
                    amount = p2b['amount'] / check_curr['rate']
                    currency = p2b['curr_id'][0]
                    amount_currency = p2b['amount']
                move = {
                    'journal_id':p2b['journal_id'][0],
                    'period_id':p2b['period_id'][0],
                    'date':p2b['date'],
                    }
                move_id = move_pool.create(cr, uid, move)
                name = p2b['dest_p2b_account'][1] +' debit ' +str(p2b['amount'])
                check_bank = self.pool.get('res.partner.bank').read(cr, uid, p2b['dest_p2b_account'][0],['account_id'])
                account_id = check_bank['account_id'][0] 
                debit = {
                    'name':name,
                    'journal_id':p2b['journal_id'][0],
                    'period_id':p2b['period_id'][0],
                    'date':p2b['date'],
                    'account_id':account_id,
                    'debit':amount,
                    'currency_id':currency,
                    'amount_currency':amount_currency,
                    'move_id':move_id,
                    }
                move_line_pool.create(cr, uid, debit)
                pc_id = p2b['pettycash_id'][0]
                pettycash_account = self.pool.get('account.pettycash').read(cr, uid, pc_id,['account_code'])
                name = pettycash_account['account_code'][1] +' credit ' +str(p2b['amount'])
                credit = {
                    'name':name,
                    'journal_id':p2b['journal_id'][0],
                    'period_id':p2b['period_id'][0],
                    'date':p2b['date'],
                    'account_id':pettycash_account['account_code'][0],
                    'credit':amount,
                    'currency_id':currency,
                    'amount_currency':amount_currency,
                    'move_id':move_id,
                    }
                move_line_pool.create(cr, uid, credit)
                move_pool.post(cr, uid, [move_id],context={})
                result = {
                        'move_id':move_id,
                        'state':'done',
                        }
                self.write(cr, uid, p2b['id'],result)
            if p2b['amount']==0.00:
                raise osv.except_osv(_('Error !'), _('You cannot create a transfer with no amount!'))
        return True
                
    def transfer(self, cr, uid, ids, context=None):
        for transfer in self.read(cr, uid, ids, context=None):
            if transfer['type']=='b2b':
                self.b2b_transfer(cr, uid, [transfer['id']])
            elif transfer['type']=='p2b':
                self.p2b_transfer(cr, uid, [transfer['id']])
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        for transfer in self.read(cr, uid, ids, context=None):
            if transfer['state']=='draft':
                self.write(cr, uid, transfer['id'],{'state':'cancel'})
            elif transfer['state']=='done':
                move_id = transfer['move_id'][0]
                move_pool.unlink(cr, uid, [move_id])
                self.write(cr, uid, transfer['id'],{'state':'cancel'})
        return True
    def set_to_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'draft'})
fund_transfer()

class pettycash_denom(osv.osv):
    _inherit = 'pettycash.denom'
    _columns = {
        'ft_id':fields.many2one('fund.transfer','Fund Transfer ID',ondelete='cascade'),
        }
pettycash_denom()

class ft(osv.osv):
    _inherit='fund.transfer'
    _columns={
        'denom_ids':fields.one2many('pettycash.denom','ft_id','Denomination Breakdown'),
        }
ft()

class internal_account_transfer(osv.osv):
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'iat')],limit=1)
        return res and res[0] or False
    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'internal.account.transfer'
    _description = 'Internal Account Transfers'
    _columns = {
        'name':fields.char('Transfer ID',size=32),
        'remarks':fields.text('Remarks'),
        'date':fields.date('Date'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal',domain=[('type','=','iat')]),
        'src_pat_analytic_id':fields.many2one('account.analytic.account','PAT Account',domain=[('supplier','=',True)]),
        'src_income_analytic_id':fields.many2one('account.analytic.account','Income Account',domain=[('ntm_type','=','income')]),
        'src_expense_analytic_id':fields.many2one('account.analytic.account','Expense Account',domain=[('ntm_type','=','expense')]),
        'src_proj_analytic_id':fields.many2one('account.analytic.account','Project Account', domain=[('project','=',True)]),
        'dest_pat_analytic_id':fields.many2one('account.analytic.account','PAT Account', domain=[('supplier','=',True)]),
        'dest_proj_analytic_id':fields.many2one('account.analytic.account','Project Account', domain=[('project','=',True)]),
        'dest_income_analytic_id':fields.many2one('account.analytic.account','Income Account', domain=[('ntm_type','=','income')]),
        'transfer_type':fields.selection([
                                ('people2proj','PAT to Project Account'),
                                ('proj2proj','Project to Project Account'),
                                ('people2people','PAT to PAT Account'),
                                ('proj2people','Project to PAT Account'),
                                ('people2pc','PAT to Petty Cash Account'),
                                ('people2income','PAT to Income'),
                                ('proj2income','Project to Income'),
                                ('expense2income','Expense to Income'),
                                ('proj2pc','Project to Petty Cash Account'),
                                ('income2pc','Income to Petty Cash Account'),
                                ('expense2people','Expense to PAT Account'),
                                ('expense2proj','Expense to Project Account'),
                                ],'Transfer Type'),
        'bank_account':fields.many2one('res.partner.bank','Bank Account'),
        'amount':fields.float('Amount'),
        'currency_id':fields.many2one('res.currency','Currency'),
        'multiple':fields.boolean('Multiple Destination'),
        'distribute_type':fields.selection([
                                ('fixed','Fixed Amount'),
                                ('percentage','Percentage'),
                                ('equal','Equally Distributed'),
                                ],'Distribution Type'),
        'pettycash_id':fields.many2one('account.pettycash', 'Petty Cash Account'),
        'state': fields.selection([
            ('draft','Draft'),
            ('transfer','Transferred'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        }
    _defaults = {
            'date':lambda *a: time.strftime('%Y-%m-%d'),
            'period_id':_get_period,
            'journal_id':_get_journal,
            'currency_id':'base.PHP',
            'distribute_type':'fixed',
            'state':'draft',
            }
    
    def onchange_multiple(self, cr, uid, ids, multiple=False):
        result = {}
        if multiple:
            for iat in self.read(cr, uid, ids, context=None):
                for iatd_id in iat['pat_iatd_ids']: 
                    self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
            result = {'value':{'dest_pat_analytic_id':False,'dest_proj_analytic_id':False,'distribute_type':False}}
        if not multiple:
            for iat in self.read(cr, uid, ids, context=None):
                for iatd_id in iat['pat_iatd_ids']: 
                    self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
            result = {'value':{'dest_pat_analytic_id':False,'dest_proj_analytic_id':False,'distribute_type':False}}
        return result
    
    def onchange_amount(self, cr, uid, ids, amount=False,distribute_type=False):
        result={}
        new_iatd = []
        iatd_ids = []
        acc_ids = []
        pat_id = False
        proj_id = False
        pat_bool = False
        income_bool = False
        income_id = False
        if amount>0.00:
            for iat in self.read(cr, uid, ids, context=None):
                if distribute_type in ['fixed','percentage']:
                    if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                        iatd_ids = iat['proj_iatd_ids']
                        pat_id = False
                        pat_bool = False
                        proj_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id'])
                            acc_ids.append(iatd_read['proj_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                        iatd_ids = iat['pat_iatd_ids']
                        pat_id = iat['id']
                        proj_id = False
                        pat_bool = True
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id'])
                            acc_ids.append(iatd_read['pat_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                        iatd_ids = iat['income_iatd_ids']
                        pat_id = False
                        proj_id = False
                        pat_bool = False
                        income_bool = True
                        income_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                            acc_ids.append(iatd_read['income_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    for acc_id in acc_ids:
                        proj_analytic = False
                        pat_analytic = False
                        income_analytic = False
                        if pat_bool==False and income_bool==False:
                            pat_analytic = False
                            proj_analytic = acc_id
                        if pat_bool==False and income_bool==True:
                            pat_analytic = False
                            proj_analytic = False
                            income_analytic = acc_id
                        elif pat_bool==True:
                            pat_analytic = acc_id
                            proj_analytic = False
                            income_analytic = False
                        new_iatd_ids = {
                            'proj_analytic_id':proj_analytic,
                            'pat_analytic_id':pat_analytic,
                            'income_analytic_id':income_analytic,
                            'amount':'0.00',
                            'pat_iat_id':pat_id,
                            'proj_iat_id':proj_id,
                            'income_iat_id':income_id,
                            }
                        new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                        new_iatd.append(new_iatd_id)
                    if pat_bool==False and income_bool==False:
                        result = {'value':{'proj_iatd_ids':new_iatd}}
                    if pat_bool==False and income_bool==True:
                        result = {'value':{'income_iatd_ids':new_iatd}}
                    if pat_bool==True:
                        result = {'value':{'pat_iatd_ids':new_iatd}}
                if distribute_type=='equal':
                    if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                        iatd_ids = iat['proj_iatd_ids']
                        pat_id = False
                        pat_bool = False
                        proj_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id', ])
                            acc_ids.append(iatd_read['proj_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                        iatd_ids = iat['pat_iatd_ids']
                        pat_id = iat['id']
                        proj_id = False
                        pat_bool = True
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id', ])
                            acc_ids.append(iatd_read['pat_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                        iatd_ids = iat['income_iatd_ids']
                        pat_id = False
                        proj_id = False
                        pat_bool = False
                        income_bool = True
                        income_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                            acc_ids.append(iatd_read['income_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    dest_len = len(iatd_ids)
                    amt = amount/dest_len
                    ctr=0
                    amt = "%.2f" % amt
                    amt = float(amt)
                    check_amt = amt * dest_len
                    check_amt = "%.2f" % check_amt
                    check_amt = float(check_amt)
                    check_amt = amount - check_amt
                    for acc_id in acc_ids:
                        proj_analytic = False
                        pat_analytic = False
                        income_analytic = False
                        if pat_bool==False and income_bool==False:
                            pat_analytic = False
                            proj_analytic = acc_id
                        if pat_bool==False and income_bool==True:
                            pat_analytic = False
                            proj_analytic = False
                            income_analytic = acc_id
                        elif pat_bool==True:
                            pat_analytic = acc_id
                            proj_analytic = False
                            income_analytic = False
                        if ctr==0:
                            amt = amt + check_amt
                            new_iatd_ids = {
                                'proj_analytic_id':proj_analytic,
                                'pat_analytic_id':pat_analytic,
                                'income_analytic_id':income_analytic,
                                'amount':amt,
                                'pat_iat_id':pat_id,
                                'proj_iat_id':proj_id,
                                'income_iat_id':income_id,
                                }
                            ctr=1
                            new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                            new_iatd.append(new_iatd_id)
                        elif ctr==1:
                            amt = amount/dest_len
                            amt = "%.2f" % amt
                            new_iatd_ids = {
                                'proj_analytic_id':proj_analytic,
                                'pat_analytic_id':pat_analytic,
                                'income_analytic_id':income_analytic,
                                'amount':amt,
                                'pat_iat_id':pat_id,
                                'proj_iat_id':proj_id,
                                'income_iat_id':income_id,
                                }
                            new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                            new_iatd.append(new_iatd_id)
                    if pat_bool==False and income_bool==False:
                        result = {'value':{'proj_iatd_ids':new_iatd}}
                    if pat_bool==False and income_bool==True:
                        result = {'value':{'income_iatd_ids':new_iatd}}
                    if pat_bool==True:
                        result = {'value':{'pat_iatd_ids':new_iatd}}
        return result
    
    def onchange_distribution(self, cr, uid, ids, distribute_type=False,amount=False):
        result={}
        new_iatd = []
        iatd_ids = []
        acc_ids = []
        pat_id = False
        proj_id = False
        income_id = False
        income_bool = False
        pat_bool = False
        if distribute_type in ['fixed','percentage']:
            for iat in self.read(cr, uid, ids, context=None):
                if amount<=0.00:
                    raise osv.except_osv(_('Error !'), _('Please indicate amount!'))
                if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                    iatd_ids = iat['proj_iatd_ids']
                    pat_id = False
                    pat_bool = False
                    proj_id = iat['id']
                    income_bool = False
                    income_id = False
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id'])
                        acc_ids.append(iatd_read['proj_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                    iatd_ids = iat['pat_iatd_ids']
                    pat_id = iat['id']
                    proj_id = False
                    pat_bool = True
                    income_bool = False
                    income_id = False
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id'])
                        acc_ids.append(iatd_read['pat_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                    iatd_ids = iat['income_iatd_ids']
                    pat_id = False
                    proj_id = False
                    pat_bool = False
                    income_bool = True
                    income_id = iat['id']
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                        acc_ids.append(iatd_read['income_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                for acc_id in acc_ids:
                    proj_analytic = False
                    pat_analytic = False
                    income_analytic = False
                    if pat_bool==False and income_bool==False:
                        pat_analytic = False
                        proj_analytic = acc_id
                    if pat_bool==False and income_bool==True:
                        pat_analytic = False
                        proj_analytic = False
                        income_analytic = acc_id
                    elif pat_bool==True:
                        pat_analytic = acc_id
                        proj_analytic = False
                        income_analytic = False
                    new_iatd_ids = {
                        'proj_analytic_id':proj_analytic,
                        'pat_analytic_id':pat_analytic,
                        'income_analytic_id':income_analytic,
                        'amount':'0.00',
                        'pat_iat_id':pat_id,
                        'proj_iat_id':proj_id,
                        'income_iat_id':income_id,
                        }
                    new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                    new_iatd.append(new_iatd_id)
                    if pat_bool==False and income_bool==False:
                        result = {'value':{'proj_iatd_ids':new_iatd}}
                    if pat_bool==False and income_bool==True:
                        result = {'value':{'income_iatd_ids':new_iatd}}
                    if pat_bool==True:
                        result = {'value':{'pat_iatd_ids':new_iatd}}
        if distribute_type=='equal':
            for iat in self.read(cr, uid, ids, context=None):
                if amount<=0.00:
                    raise osv.except_osv(_('Error !'), _('Please indicate amount!'))
                if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                    iatd_ids = iat['proj_iatd_ids']
                    pat_id = False
                    pat_bool = False
                    proj_id = iat['id']
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id', ])
                        acc_ids.append(iatd_read['proj_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                    iatd_ids = iat['pat_iatd_ids']
                    pat_id = iat['id']
                    proj_id = False
                    pat_bool = True
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id', ])
                        acc_ids.append(iatd_read['pat_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                    iatd_ids = iat['income_iatd_ids']
                    pat_id = False
                    proj_id = False
                    pat_bool = False
                    income_bool = True
                    income_id = iat['id']
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                        acc_ids.append(iatd_read['income_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                dest_len = len(iatd_ids)
                amt = amount/dest_len
                ctr=0
                amt = "%.2f" % amt
                amt = float(amt)
                check_amt = amt * dest_len
                check_amt = "%.2f" % check_amt
                check_amt = float(check_amt)
                check_amt = amount - check_amt
                for acc_id in acc_ids:
                    proj_analytic = False
                    pat_analytic = False
                    income_analytic = False
                    if pat_bool==False and income_bool==False:
                        pat_analytic = False
                        proj_analytic = acc_id
                    if pat_bool==False and income_bool==True:
                        pat_analytic = False
                        proj_analytic = False
                        income_analytic = acc_id
                    elif pat_bool==True:
                        pat_analytic = acc_id
                        proj_analytic = False
                        income_analytic = False
                    if ctr==0:
                        amt = amt + check_amt
                        new_iatd_ids = {
                            'proj_analytic_id':proj_analytic,
                            'pat_analytic_id':pat_analytic,
                            'income_analytic_id':income_analytic,
                            'amount':amt,
                            'pat_iat_id':pat_id,
                            'proj_iat_id':proj_id,
                            'income_iat_id':income_id,
                            }
                        ctr=1
                        new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                        new_iatd.append(new_iatd_id)
                    elif ctr==1:
                        amt = amount/dest_len
                        amt = "%.2f" % amt
                        new_iatd_ids = {
                            'proj_analytic_id':proj_analytic,
                            'pat_analytic_id':pat_analytic,
                            'income_analytic_id':income_analytic,
                            'amount':amt,
                            'pat_iat_id':pat_id,
                            'proj_iat_id':proj_id,
                            'income_iat_id':income_id,
                            }
                        new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                        new_iatd.append(new_iatd_id)
                if pat_bool==False and income_bool==False:
                    result = {'value':{'proj_iatd_ids':new_iatd}}
                if pat_bool==False and income_bool==True:
                    result = {'value':{'income_iatd_ids':new_iatd}}
                if pat_bool==True:
                    result = {'value':{'pat_iatd_ids':new_iatd}}
        return result
    
    def create(self, cr, uid, vals, context=None):
        if 'transfer_type' in context:
            if context['transfer_type']=='people2proj':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2proj'),
                })
            if context['transfer_type']=='proj2people':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2people'),
                })
            if context['transfer_type']=='people2pc':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2pc'),
                })
            if context['transfer_type']=='proj2pc':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2pc'),
                })
            if context['transfer_type']=='income2pc':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.income2pc'),
                })
            if context['transfer_type']=='people2people':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2people'),
                })
            if context['transfer_type']=='proj2proj':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2proj'),
                })
            if context['transfer_type']=='people2income':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2income'),
                })
            if context['transfer_type']=='proj2income':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2income'),
                })
            if context['transfer_type']=='expense2income':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.expense2income'),
                })
            if context['transfer_type']=='expense2people':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.expense2people'),
                })
            if context['transfer_type']=='expense2proj':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.expense2proj'),
                })
                
        return super(internal_account_transfer, self).create(cr, uid, vals, context)

internal_account_transfer()

class internal_account_transfer_destination(osv.osv):
    _name = 'internal.account.transfer.destination'
    _description = 'Internal Account Transfer Destinations'
    _columns = {
        'name':fields.char('Account Name',size=64),
        'pat_analytic_id':fields.many2one('account.analytic.account','Analytic Account',domain=[('supplier','=',True)]),
        'proj_analytic_id':fields.many2one('account.analytic.account','Analytic Account',domain=[('project','=',True)]),
        'amount':fields.float('Amount/Percentage', digits_compute=dp.get_precision('Account')),
        'proj_iat_id':fields.many2one('internal.account.transfer','Transfer ID',ondelete='cascade'),
        'pat_iat_id':fields.many2one('internal.account.transfer','Transfer ID',ondelete='cascade'),
        'income_iat_id':fields.many2one('internal.account.transfer','Transfer ID', ondelete='cascade'),
        'expense_iat_id':fields.many2one('internal.account.transfer','Transfer ID', ondelete='cascade'),
        'income_analytic_id':fields.many2one('account.analytic.account','Analytic Account',domain=[('ntm_type','=','income')]),
        'remarks':fields.text('Remarks'),
        'percentage':fields.float('Percentage(%)'),
        'percentage_bool':fields.boolean('Percentage?'),
        }
    
    def onchange_percentage(self,cr, uid, ids, percentage=False):
        result = {}
        if percentage:
            amount = 0.00
            for iatd in self.read(cr, uid, ids, context=None):
                if iatd['proj_iat_id']:
                    iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['proj_iat_id'][0],['amount'])
                    amount = iat_read['amount']
                elif iatd['pat_iat_id']:
                    iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['pat_iat_id'][0],['amount'])
                    amount=iat_read['amount']
            amount = (amount * percentage) / 100
            result = {'value':{
                'amount':amount,
                }
            }
        return result 
    
    def write(self,cr, uid,ids,vals, context=None):
        if 'percentage' in vals:
            amount = 0.00
            for iatd in self.read(cr, uid, ids, context=None):
                if iatd['proj_iat_id']:
                    iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['proj_iat_id'][0],['amount'])
                    amount = iat_read['amount']
                elif iatd['pat_iat_id']:
                    iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['pat_iat_id'][0],['amount'])
                    amount=iat_read['amount']
            amount = (amount * vals['percentage']) / 100
            vals['amount']=amount
        return super(internal_account_transfer_destination,self).write(cr, uid,ids, vals,context=None)
                    
                
    
internal_account_transfer_destination()


class pcdenom(osv.osv):
    _inherit = 'pettycash.denom'
    _columns = {
        'iat_id':fields.many2one('internal.account.transfer','IAT ID', ondelete='cascade'),
        }
pcdenom()
class iat(osv.osv):
    _inherit = 'internal.account.transfer'
    _columns = {
        'pat_iatd_ids':fields.one2many('internal.account.transfer.destination','pat_iat_id','Destinations'),
        'proj_iatd_ids':fields.one2many('internal.account.transfer.destination','proj_iat_id','Destinations'),
        'income_iatd_ids':fields.one2many('internal.account.transfer.destination','income_iat_id','Destinations'),
        'denom_ids':fields.one2many('pettycash.denom','iat_id','Denominations'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Releasing Journal Items', readonly=True),
        }
    
    def onchange_curr(self, cr, uid, ids, currency_id=False):
        result = {}
        if currency_id:
            for iat in self.read(cr, uid, ids, context=None):
                if iat['transfer_type']=='people2pc':
                    result = {'value':{'pettycash_id':False}}
        return result
    
    def onchange_pcid(self, cr, uid, ids, pettycash_id=False, context=None):
        result = {}
        if pettycash_id:
            iat_ids = ids
            iat_id = iat_ids[0]
            pc_read = self.pool.get('account.pettycash').read(cr,uid, pettycash_id, ['currency_id'])
            denom_search = self.pool.get('denominations').search(cr, uid, [('currency_id','=',pc_read['currency_id'][0])])
            currency = pc_read['currency_id'][1]
            if not denom_search:
                raise osv.except_osv(_('Error!'), _('%s has no available denominations.Please add them!')%currency)
            elif denom_search:
                denominations = []
                denom_del = self.pool.get('pettycash.denom').search(cr, uid, [('iat_id','=',iat_id)])
                self.pool.get('pettycash.denom').unlink(cr, uid, denom_del)
                for denom in denom_search:
                    vals = {
                        'name':denom,
                        'iat_id':iat_id,
                        }
                    newd = self.pool.get('pettycash.denom').create(cr, uid, vals)
                    denominations.append(newd)
                result = {'values':{'denom_ids':denominations}}
            return result
iat()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,