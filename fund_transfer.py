import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from stringprep import b1_set

class b2b_fund_transfer(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'b2b.fund.transfer'
    _description = "Fund Transfers"
    _columns = {
        'name':fields.char('Transfer ID',size=64,readonly=True),
        'date':fields.date('Transfer Date'),
        'release_date':fields.date('Release Date'),
        'receive_date':fields.date('Receive Date'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal', required=True),
        'src_account':fields.many2one('res.partner.bank','Source Bank Account'),
        'amount':fields.float('Amount to Transfer'),
        'dest_account':fields.many2one('res.partner.bank','Destination Bank Account'),
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
                            ],'State'),
        }
    
    _defaults = {
        'period_id':_get_period,
        'state':'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        }
    
    def request(self, cr, uid, ids, context=None):
        for b2b in self.read(cr, uid, ids, context=None):
            if b2b['src_account'][0]==b2b['dest_account'][0]:
                raise osv.except_osv(_('Error!'), _('IBT-001: Source and Destinations accounts are the same!'))
            elif b2b['src_account'][0]!=b2b['dest_account'][0]:
                if b2b['amount']<=0:
                    raise osv.except_osv(_('Error!'), _('IBT-002: Amount less than or equal to ZERO is not allowed!'))
                elif b2b['amount']>0:
                    name = self.pool.get('ir.sequence').get(cr, uid, 'internal.bank.transfer')
                    self.write(cr, uid, ids, {'state':'requested','name':name})
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
            'model':'b2b.fund.transfer',
            'form':data
            }
        return {'type': 'ir.actions.report.xml','report_name': 'internal.fund.transfer','nodestroy':True,'datas': datas,'header':False,}
    
    def release(self, cr, uid, ids, context=None):
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
    
    def receive(self, cr, uid, ids, context=None):
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

b2b_fund_transfer()

class pettycash_denom(osv.osv):
    _inherit = 'pettycash.denom'
    _columns = {
        'b2b_id':fields.many2one('b2b.fund.transfer','Transfer ID',ondelete='cascade'),
        }
pettycash_denom()

class ft(osv.osv):
    _inherit='b2b.fund.transfer'
    _columns={
        'denom_ids':fields.one2many('pettycash.denom','b2b_id','Denomination Breakdown'),
        }
ft()

class p2b_fund_transfer(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'p2b.fund.transfer'
    _description = "Petty Cash to Bank Fund Transfer"
    _columns = {
        'name':fields.char('Transfer ID',size=64,readonly=True),
        'date':fields.date('Transfer Date'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal', required=True),
        'pettycash_id':fields.many2one('account.pettycash','Petty Cash Account'),
        'amount':fields.float('Amount to Transfer'),
        'currency_id':fields.many2one('res.currency', 'Currency'),
        'dest_p2b_account':fields.many2one('res.partner.bank','Destination Bank Account'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Releasing Journal Items', readonly=True),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('done','Transferred'),
                            ('cancel','Cancelled'),
                            ],'State'),
        'enabled':fields.boolean('Enabled'),
        }
    
    _defaults = {
        'period_id':_get_period,
        'state':'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'p2btf'),
        })
        return super(p2b_fund_transfer, self).create(cr, uid, vals, context)
    
    def enableAccounts(self,cr, uid, ids, context=None):
        for transfer in self.read(cr, uid, ids,context=None):
            currency_denoms = self.pool.get('denominations').search(cr, uid, [('currency_id','=',transfer['currency_id'][0])])
            for denom in currency_denoms:
                vals = {
                    'p2b_id':transfer['id'],
                    'name':denom,
                    }
                self.pool.get('pettycash.denom').create(cr, uid, vals)
            self.write(cr, uid, ids, {'enabled':True})
        return True
    
    def transfer(self, cr, uid, ids, context=None):
        uidRead = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
        companyRead = self.pool.get('res.company').read(cr, uid, uidRead['company_id'][0],['currency_id'])
        for transfer in self.read(cr, uid, ids, context=None):
            amount = False
            amount_currency = False
            pcChecker = self.pool.get('account.pettycash').read(cr, uid, transfer['pettycash_id'][0],['amount'])
            if pcChecker['amount']<=0.00:
                raise osv.except_osv(_('Error !'), _('P2BFT-001: Insufficient Funds on the chosen petty cash account!'))
            elif pcChecker['amount']>0.00:
                transfer_denoms = self.pool.get('pettycash.denom').search(cr, uid, [('p2b_id','=',transfer['id']),('quantity','>',0.00)])
                if not transfer_denoms:
                    raise osv.except_osv(_('Error !'), _('P2BFT-002: Please change the quantity of the denomination to be deducted from the petty cash account!'))
                for denom in transfer['denom_ids']:
                    denom_check = self.pool.get('pettycash.denom').read(cr, uid, denom,['name','quantity','amount'])
                    if denom_check['quantity'] == 0.00:
                        continue
                    if denom_check['quantity'] < 0.00:
                        raise osv.except_osv(_('Error !'), _('P2BFT-003: Negative quantity on denomination list is not allowed!'))
                    if denom_check['quantity'] > 0.00:
                        pettycash_name = transfer['pettycash_id'][1]
                        denom_name = denom_check['name'][1]
                        quanti = denom_check['quantity']
                        ptc_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_check['name'][0]),
                                                                                        ('pettycash_id','=',transfer['pettycash_id'][0]),
                                                                                        ('quantity','>=',denom_check['quantity'])])
                        if not ptc_denom_check:
                            raise osv.except_osv(_('Error !'), _('P2BFT-004: The quantity of %s denomination of petty cash %s is less than the requested quantity to be transferred!')%(denom_name, pettycash_name))
                        else:
                            amount_currency +=denom_check['amount']
                            ptc_denom_check2 = self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',transfer['pettycash_id'][0]),('name','=',denom_check['name'][0])])
                            ptc_denomRead = self.pool.get('pettycash.denom').read(cr, uid, ptc_denom_check2[0],['quantity'])
                            new_qty = ptc_denomRead['quantity'] - quanti
                            self.pool.get('pettycash.denom').write(cr, uid, ptc_denom_check2[0],{'quantity':new_qty})
                if companyRead['currency_id'][0]!=transfer['currency_id'][0]:
                    checkCurr = self.pool.get('res.currency').read(cr, uid, transfer['currency_id'][0],['rate'])
                    amount = amount_currency / checkCurr['rate']
                elif companyRead['currency_id'][0]==transfer['currency_id'][0]:
                    amount = amount_currency
                move= {'journal_id':transfer['journal_id'][0],'period_id':transfer['period_id'][0],'date':transfer['date'],}
                move_id = self.pool.get('account.move').create(cr, uid, move)
                name = transfer['dest_p2b_account'][1] + ' debit ' + str(transfer['amount'])
                check_bank = self.pool.get('res.partner.bank').read(cr, uid, transfer['dest_p2b_account'][0],['account_id'])
                move.update({'name':name,'account_id':check_bank['account_id'][0],'debit':amount,'credit':0.00,'currency_id':transfer['currency_id'][0],'amount_currency':amount_currency,'move_id':move_id,})
                self.pool.get('account.move.line').create(cr, uid, move)
                pettycash_account = self.pool.get('account.pettycash').read(cr, uid, transfer['pettycash_id'][0],['account_code'])
                name = pettycash_account['account_code'][1] +' credit ' +str(transfer['amount'])
                move.update({'name':name,'account_id':pettycash_account['account_code'][0],'debit':0.00,'credit':amount,'currency_id':transfer['currency_id'][0],'amount_currency':amount_currency,'move_id':move_id,})
                self.pool.get('account.move.line').create(cr, uid, move)
                self.pool.get('account.move').post(cr, uid, [move_id])
                result = {'move_id':move_id,'state':'done','amount':amount_currency}
                self.write(cr, uid, ids, result)
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        for transfer in self.read(cr, uid, ids, context=None):
            if transfer['state']=='draft':
                self.write(cr, uid, transfer['id'],{'state':'cancel'})
            elif transfer['state']=='done':
                move_id = transfer['move_id'][0]
                self.pool.get('account.move').button_cancel(cr, uid, [move_id])
                self.pool.get('account.move').unlink(cr, uid, [move_id])
                transfer_denoms = self.pool.get('pettycash.denom').search(cr, uid, [('p2b_id','=',transfer['id']),('quantity','>',0.00)])
                for denom in transfer_denoms:
                    denom_check = self.pool.get('pettycash.denom').read(cr, uid, denom, ['name','quantity'])
                    pettycashDenomination = self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',transfer['pettycash_id'][0]),
                                                                                              ('name','=',denom_check['name'][0])])
                    pcdenomReader = self.pool.get('pettycash.denom').read(cr, uid, pettycashDenomination[0],['quantity'])
                    new_qty = pcdenomReader['quantity'] + denom_check['quantity']
                    self.pool.get('pettycash.denom').write(cr, uid, pettycashDenomination[0],{'quantity':new_qty})
                self.write(cr, uid, transfer['id'],{'state':'cancel'})
        return True
p2b_fund_transfer()

class p2b_pettycash_denom(osv.osv):
    _inherit = 'pettycash.denom'
    _columns = {
        'p2b_id':fields.many2one('p2b.fund.transfer','Fund Transfer ID',ondelete='cascade'),
        }
p2b_pettycash_denom()

class p2bft(osv.osv):
    _inherit='p2b.fund.transfer'
    _columns={
        'denom_ids':fields.one2many('pettycash.denom','p2b_id','Denomination Breakdown'),
        }
p2bft()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,