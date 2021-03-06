import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class bill_exchange(osv.osv):
    
    _name = 'bill.exchange'
    _description = "Bills Exchange"
    _columns = {
        'name':fields.char('Exchange#',size=64, readonly=True),
        'date':fields.date('Exchange Date'),
        'currency_id':fields.many2one('res.currency','Currency'),
        'pettycash_id':fields.many2one('account.pettycash','Petty Cash'),
        'filled':fields.boolean('Filled'),
        'state':fields.selection([
                        ('draft','Draft'),
                        ('done','Done'),
                        ],'State',readonly=True),
        }
    
    _defaults = {
            'state':'draft',
            'date': lambda *a: time.strftime('%Y-%m-%d'),
            }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'bill.exchange'),
        })
        return super(bill_exchange, self).create(cr, uid, vals, context)
    
    def on_change_pca(self, cr, uid, ids, pettycash_id=False):
        result = {}
        currency_id=0
        if pettycash_id:
            pettycash = self.pool.get('account.pettycash').browse(cr, uid, pettycash_id)
            currency_id = pettycash.currency_id.id
            result = {'value':{
                    'currency_id':currency_id,
                      }
                }
        return result
    
    def fill(self, cr, uid, ids, context=None):
        for pcr in self.read(cr, uid, ids, context=None):
            curr_id = pcr['currency_id'][0]
            currency = pcr['currency_id'][1]
            denoms = self.pool.get('denominations').search(cr, uid, [('currency_id','=',curr_id)])
            if not denoms:
                raise osv.except_osv(_('Error !'), _('BE-001: %s has no available denominations.Please add them!')%currency)
            if denoms:
                for denom in denoms:
                    values = {
                        'name':denom,
                        'be_id':pcr['id'],
                    }
                    self.pool.get('pettycash.denom').create(cr, uid, values)
                    values = {
                        'name':denom,
                        'be_id2':pcr['id'],
                    }
                    self.pool.get('pettycash.denom').create(cr, uid, values)
            self.write(cr, uid,pcr['id'],{'filled':True})
        return True
    
    def exchange(self, cr, uid, ids, context=None):
        for be in self.read(cr, uid, ids, context=None):
            cash_in_search = self.pool.get('pettycash.denom').search(cr, uid, [('be_id','=',be['id']),('quantity','>',0)])
            cash_out_search = self.pool.get('pettycash.denom').search(cr, uid, [('be_id2','=',be['id']),('quantity','>',0)])
            if not cash_in_search:
                raise osv.except_osv(_('Error !'), _('BE-002: Please indicate the quantities of the denominations to be exchanged!'))
            if not cash_out_search:
                raise osv.except_osv(_('Error !'), _('BE-003: Please indicate the quantities of the denominations to be released!'))
            if cash_in_search and cash_out_search:
                cash_in_amount = 0
                cash_out_amount = 0
                for cash_in_id in cash_in_search:
                    cash_in_read = self.pool.get('pettycash.denom').read(cr, uid, cash_in_id, ['name', 'quantity'])
                    denom_read = self.pool.get('denominations').read(cr, uid, cash_in_read['name'][0],['multiplier'])
                    cash_in_amount +=cash_in_read['quantity'] * denom_read['multiplier']
                for cash_out_id in cash_out_search:
                    cash_out_read = self.pool.get('pettycash.denom').read(cr, uid, cash_out_id, ['name', 'quantity'])
                    denom_read = self.pool.get('denominations').read(cr, uid, cash_out_read['name'][0],['multiplier'])
                    cash_out_amount +=cash_out_read['quantity'] * denom_read['multiplier']
                if cash_in_amount != cash_out_amount:
                    raise osv.except_osv(_('Error !'), _('BE-004: Total amounts are not equal!'))
                elif cash_in_amount==cash_out_amount:
                    pc_id = be['pettycash_id'][0]
                    for cash_in_id in cash_in_search:
                        cash_in_read = self.pool.get('pettycash.denom').read(cr, uid, cash_in_id, ['name', 'quantity'])
                        pc_search = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',cash_in_read['name'][0]),('pettycash_id','=',pc_id)])
                        for denom_id in pc_search:
                            denom_reader = self.pool.get('pettycash.denom').read(cr, uid, denom_id,['quantity'])
                            new_qty = denom_reader['quantity'] + cash_in_read['quantity'] 
                            self.pool.get('pettycash.denom').write(cr, uid, denom_id,{'quantity':new_qty})
                    for cash_out_id in cash_out_search:
                        cash_out_read = self.pool.get('pettycash.denom').read(cr, uid, cash_out_id, ['name', 'quantity'])
                        pc_search = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',cash_out_read['name'][0]),('pettycash_id','=',pc_id)])
                        for denom_id in pc_search:
                            denom_reader = self.pool.get('pettycash.denom').read(cr, uid, denom_id,['quantity','name'])
                            denomination = denom_reader['name'][1]
                            if denom_reader['quantity'] < cash_out_read['quantity']:
                                raise osv.except_osv(_('Error !'), _('BE-005: Quantity to be release is greater than the cash on petty cash for denomination %s!')%denomination)
                            else:
                                new_qty = denom_reader['quantity'] - cash_out_read['quantity'] 
                                self.pool.get('pettycash.denom').write(cr, uid, denom_id,{'quantity':new_qty})
                    self.write(cr, uid, ids, {'state':'done'})
        return True 
    
                    
bill_exchange()

class account_pettycash_liquidation(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    _name = "account.pettycash.liquidation"
    _description = "Liquidation"
    _columns = {
        'name':fields.char('Liquidation ID', size=64),
        'date':fields.date('Date'),
        'denom_filled':fields.boolean('Filled?'),
        'pc_id':fields.many2one('account.pettycash','PC Account'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'amount':fields.float('Total Amount'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Releasing Journal Items', readonly=True),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirmed','Confirmed'),
            ('completed','Completed'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        }
    _defaults = {
            'name':'NEW',
            'state':'draft',
            'amount':0.00,
            'period_id':_get_period,
            }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'account.pettycash.liquidation'),
        })
        return super(account_pettycash_liquidation, self).create(cr, uid, vals, context)
    
account_pettycash_liquidation()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pcl_id':fields.many2one('account.pettycash.liquidation','Liquidation',ondelete="cascade"),
        'be_id':fields.many2one('bill.exchange','Bill Exchange',ondelete="cascade"),
        'be_id2':fields.many2one('bill.exchange','Bill Exchange',ondelete="cascade"),
        }
pettycash_denom()

class pc_income_lines(osv.osv):
    _name = 'pc.income.lines'
    _description = "Income Lines"
    _columns = {
        'name':fields.char('Description',size=64),
        'amount':fields.float('Amount'),
        'reference':fields.char('Reference',size=64),
        'pcl_id':fields.many2one('account.pettycash.liquidation','Liquidation',ondelete="cascade"),
        'analytic_id':fields.many2one('account.analytic.account','Account'),
        'account_id':fields.many2one('account.account','Account'),
        'acc_name':fields.char('Account Name',size=64),
        'type':fields.selection([
                            ('analytic','Analytic Account'),
                            ('normal','Normal Account')
                            ],'Account Type',required=True),
        }
    
    _defaults = {
        'type':'analytic',
        }
    
    def data_get(self, cr, uid, ids, context=None):
        datas = {}
        statements = []
        if context is None:
            context = {}
        for data in self.read(cr, uid, ids, context=None):
            rec = data['id']
            attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','pc.income.lines'),('res_id','=',rec)])
            self.pool.get('ir.attachment').unlink(cr, uid, attachments)
            statements.append(rec)
        datas = {
            'ids':statements,
            'model':'pc.income.lines',
            'form':data
            }
        new_name = data['acc_name'] + ' ' + data['name']
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pc.income.lines',
            'nodestroy':True,
            'datas': datas,
            'name':new_name,
            'header':True,
            }
    
    def onchange_type(self, cr, uid, ids, type=False):
        result = {}
        if type:
            result = {'value':
                      {'analytic_id':False,
                       'account_id':False,}
                }
        return result
    
    def onchange_account(self, cr, uid, ids, account_id=False, analytic_id=False):
        result = {}
        if account_id and not analytic_id:
            account_read = self.pool.get('account.account').read(cr, uid, account_id,['name'])
            acc_name = account_read['name']
            self.write(cr, uid, ids, {'analytic_id':False})
            result = {'value':{'acc_name':acc_name,}}
        if analytic_id and not account_id:
            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, analytic_id,['name'])
            acc_name = analytic_read['name']
            self.write(cr, uid, ids, {'account_id':False})
            result = {'value':{'acc_name':acc_name,}}
        return result
    
pc_income_lines()

class pc_liquidation_lines(osv.osv):
 
    _name = 'pc.liquidation.lines'
    _description = "Liquidation Lines"
    _columns = {
        'name':fields.char('Description',size=64),
        'amount':fields.float('Amount'),
        'reference':fields.char('Reference',size=64),
        'pcl_id':fields.many2one('account.pettycash.liquidation','Liquidation',ondelete="cascade"),
        'analytic_id':fields.many2one('account.analytic.account','Account'),
        'account_id':fields.many2one('account.account','Account'),
        'acc_name':fields.char('Account Name',size=64),
        'type':fields.selection([
                            ('analytic','Analytic Account'),
                            ('normal','Normal Account')
                            ],'Account Type',required=True),
        }
    
    _defaults = {
        'type':'analytic',
        }
    
    def data_get(self, cr, uid, ids, context=None):
        datas = {}
        statements = []
        if context is None:
            context = {}
        for data in self.read(cr, uid, ids, ['id']):
            rec = data['id']
            attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','pc.liquidation.lines'),('res_id','=',rec)])
            self.pool.get('ir.attachment').unlink(cr, uid, attachments)
            statements.append(rec)
        datas = {
            'ids':statements,
            'model':'pc.liquidation.lines',
            'form':data
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pc.liquidation.lines',
            'nodestroy':True,
            'datas': datas,
            #'name':data['name'],
            'header':False,
            }
    
    def onchange_type(self, cr, uid, ids, type=False):
        result = {}
        if type:
            result = {'value':
                      {'analytic_id':False,
                       'account_id':False,}
                }
        return result
    
    def onchange_account(self, cr, uid, ids, account_id=False, analytic_id=False):
        result = {}
        if account_id and not analytic_id:
            account_read = self.pool.get('account.account').read(cr, uid, account_id,['name'])
            acc_name = account_read['name']
            self.write(cr, uid, ids, {'analytic_id':False})
            result = {'value':{'acc_name':acc_name,}}
        if analytic_id and not account_id:
            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, analytic_id,['name'])
            acc_name = analytic_read['name']
            self.write(cr, uid, ids, {'account_id':False})
            result = {'value':{'acc_name':acc_name,}}
        return result
pc_liquidation_lines()

class pcll_lines(osv.osv):
    _name = 'pc.liquidation.line.lines'
    _columns = {
        'name':fields.char('Description',size=64),
        'amount':fields.float('Amount'),
        'pcll_id':fields.many2one('pc.liquidation.lines','PC Liquidation Line',ondelete='cascade')
        }
pcll_lines()

class pcil_lines(osv.osv):
    _name = 'pc.income.line.lines'
    _columns = {
        'name':fields.char('Description',size=64),
        'amount':fields.float('Amount'),
        'pcil_id':fields.many2one('pc.income.lines','Income Lines',ondelete='cascade')
        }
pcil_lines()

class pcll(osv.osv):
    _inherit = 'pc.liquidation.lines'
    _columns = {
        'multiple':fields.boolean('Multiple'),
        'pclll_ids':fields.one2many('pc.liquidation.line.lines','pcll_id','Distribution'),
        }
    
    def compute(self, cr, uid, ids, context=None):
        for pcll in self.read(cr, uid, ids, context=None):
            total = False
            for line in pcll['pclll_ids']:
                reader = self.pool.get('pc.liquidation.line.lines').read(cr, uid, line, ['amount'])
                total +=reader['amount']
            self.write(cr, uid, pcll['id'], {'amount':total})
        return True
pcll()
class pcil(osv.osv):
    _inherit = 'pc.income.lines'
    _columns = {
        'multiple':fields.boolean('Multiple'),
        'pcill_ids':fields.one2many('pc.income.line.lines','pcil_id','Distribution'),
        }
    
    def compute(self, cr, uid, ids, context=None):
        for pcil in self.read(cr, uid, ids, context=None):
            total = False
            for line in pcil['pcill_ids']:
                reader = self.pool.get('pc.income.line.lines').read(cr, uid, line, ['amount'])
                total +=reader['amount']
            self.write(cr, uid, pcil['id'], {'amount':total})
        return True
pcil()

class pcl_denoms(osv.osv):
    
    def _compute_amount(self, cr, uid, ids, field, arg, context=None):
        records = self.browse(cr, uid, ids, context=context)
        result = {}
        for r in records:
            amount = r.name.multiplier * r.new_qty
            result[r.id] = amount
        return result 
    
    _inherit = 'pettycash.denom'
    _columns = {
        'new_qty':fields.integer('Present Count'),
        'new_amount': fields.function(_compute_amount, method=True, type='float', string='Total Amount', store=False),
        }
pcl_denoms()

class pcl(osv.osv):
    _inherit = "account.pettycash.liquidation"
    _columns = {
        'denom_breakdown':fields.one2many('pettycash.denom','pcl_id','Denominations Breakdown'),
        'pcll_ids':fields.one2many('pc.liquidation.lines','pcl_id','Liquidation Lines'),
        'pcil_ids':fields.one2many('pc.income.lines','pcl_id','Income Lines'),
        }
    
    def fill_denoms(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            if pcl['pc_id']:
                pc_id = self.pool.get('account.pettycash').read(cr, uid, pcl['pc_id'][0],['currency_id'])
                denom_search = self.pool.get('denominations').search(cr, uid, [('currency_id','=',pc_id['currency_id'][0])])
                currency = pc_id['currency_id'][0]
                if not denom_search:
                    raise osv.except_osv(_('Error !'), _('%s has no available denominations.Please add them!')%currency)
                if denom_search:
                    for denoms in denom_search:
                        quantity=0
                        pc_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',pcl['pc_id'][0]),('name','=',denoms)])
                        for pc_denoms in pc_denom_check:
                            pc_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pc_denoms, ['quantity'])
                            quantity = pc_denom_read['quantity']
                        values = {
                            'pcl_id':pcl['id'],
                            'name':denoms,
                            'quantity':quantity,
                            }
                        self.pool.get('pettycash.denom').create(cr, uid, values)
                self.write(cr, uid, ids,{'denom_filled':True})
            if not pcl['pc_id']:
                raise osv.except_osv(_('Error !'), _('Please add pettycash account.'))
        return True            
    
    def confirm_pcl(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            denoms = self.pool.get('pettycash.denom').search(cr, uid, [('pcl_id','=',pcl['id'])])
            liquidation_lines = self.pool.get('pc.liquidation.lines').search(cr, uid, [('pcl_id','=',pcl['id'])])
            income_lines = self.pool.get('pc.income.lines').search(cr, uid, [('pcl_id','=',pcl['id'])])
            ll_sum = 0.00
            il_sum = 0.00
            denom_sum = 0.00
            if not denoms:
                raise osv.except_osv(_('Error !'), _('You cannot confirm transactions that have no denomination lines'))
            if denoms:
                for denom in denoms:
                    denom_read = self.pool.get('pettycash.denom').read(cr, uid, denom, context=None)
                    if denom_read['new_qty']:
                        denom_reader = self.pool.get('denominations').read(cr, uid, denom_read['name'][0],['multiplier'])
                        product = denom_reader['multiplier'] * denom_read['new_qty']
                        denom_sum+=product
            if liquidation_lines:
                for line in liquidation_lines:
                    line_read = self.pool.get('pc.liquidation.lines').read(cr, uid, line, context=None)
                    if line_read['amount']<1.00:
                        raise osv.except_osv(_('Error !'), _('Liquidation lines that is less than or equal to 0.00 are not allowed'))
                    elif line_read['amount']>0.00:
                        ll_sum += line_read['amount']
            if income_lines:
                for line in income_lines:
                    income_read = self.pool.get('pc.income.lines').read(cr, uid, line, context=None)
                    if income_read['amount']<1.00:
                        raise osv.except_osv(_('Error !'), _('Income lines that is less than or equal to 0.00 are not allowed'))
                    elif income_read['amount']>0.00:
                        il_sum += income_read['amount']
            pc_read = self.pool.get('account.pettycash').read(cr, uid, pcl['pc_id'][0], ['amount'])
            pc_amount = pc_read['amount']
            check_amount = pc_amount + il_sum - ll_sum
            rec_amount = "%.2f" % check_amount
            check_amount = float(rec_amount)
            rec_amount = "%.2f" % denom_sum
            denom_sum = float(rec_amount)
            if check_amount != denom_sum:
                checker = check_amount - denom_sum
                raise osv.except_osv(_('Error !'), _('Please double check your transaction! \n There is a difference of %s on your transaction')% checker)
            elif check_amount == denom_sum:
                values = {
                        'state':'confirmed',
                        }
                self.write(cr, uid, pcl['id'], values)
        return True
    
    def update_pc(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            denoms = self.pool.get('pettycash.denom').search(cr, uid, [('pcl_id','=',pcl['id'])])
            denom_ids = []
            for denom in denoms:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, denom, context=None)
                denom_ids.append(denom_read['name'][0])
                pc_denoms = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_read['name'][0]),('pettycash_id','=',pcl['pc_id'][0])])
                for pc_denom in pc_denoms:
                    self.pool.get('pettycash.denom').write(cr, uid,pc_denom,{'quantity':denom_read['new_qty']})
            pc_denom_uninclude = self.pool.get('pettycash.denom').search(cr, uid, [('name','not in',denom_ids),('pettycash_id','=',pcl['pc_id'][0])])
            for uninclude in pc_denom_uninclude:
                self.pool.get('pettycash.denom').write(cr, uid,uninclude,{'quantity':0.00})
        return True
    
    def update_pc_cancel(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            denoms = self.pool.get('pettycash.denom').search(cr, uid, [('pcl_id','=',pcl['id'])])
            denom_ids = []
            for denom in denoms:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, denom, context=None)
                denom_ids.append(denom_read['name'][0])
                pc_denoms = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_read['name'][0]),('pettycash_id','=',pcl['pc_id'][0])])
                for pc_denom in pc_denoms:
                    self.pool.get('pettycash.denom').write(cr, uid,pc_denom,{'quantity':denom_read['quantity']})
            pc_denom_uninclude = self.pool.get('pettycash.denom').search(cr, uid, [('name','not in',denom_ids),('pettycash_id','=',pcl['pc_id'][0])])
            for uninclude in pc_denom_uninclude:
                self.pool.get('pettycash.denom').write(cr, uid,uninclude,{'quantity':0.00})
        return True
    
        
    def post_pcl(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            journal_id = pcl['journal_id'][0]
            period_id = pcl['period_id'][0]
            move_vals = {
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'date':pcl['date'],
                    'state':'draft',
                    'ref':pcl['name'],
                    } 
            move_id = self.pool.get('account.move').create(cr, uid, move_vals)
            income_amount = 0.00
            expense_amount= 0.00
            check_account = self.pool.get('account.pettycash').read(cr, uid,pcl['pc_id'][0],['account_code'])
            check_currency = self.pool.get('account.account').read(cr, uid, check_account['account_code'][0],['currency_id','company_currency_id'])
            currency = False
            rate = False
            if not check_currency['currency_id']:
                currency = check_currency['company_currency_id'][0]
                rate = 1.00
            if check_currency['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, check_currency['currency_id'][0],['rate'])
                currency = check_currency['currency_id'][0]
                rate = curr_read['rate']
            for income_line in pcl['pcil_ids']:
                account_id = False
                analytic_id = False
                line_read = self.pool.get('pc.income.lines').read(cr, uid, income_line, context=None)
                if line_read['account_id']:
                    account_id = line_read['account_id'][0]
                    analytic_id = False
                if line_read['analytic_id']:
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, line_read['analytic_id'][0],context=None)
                    analytic_name = analytic_read['name']
                    analytic_id = analytic_read['id']
                    if not analytic_read['normal_account']:
                        raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
                    if analytic_read['normal_account']:
                        account_id = analytic_read['normal_account'][0]
                if line_read['multiple']==True:
                    for line2 in line_read['pcill_ids']:
                        line2_read = self.pool.get('pc.income.line.lines').read(cr, uid, line2, context=None)
                        income_amount += line2_read['amount']
                        comp_curr_amount = line2_read['amount'] / rate
                        name = line_read['name']+' for ' +line2_read['name']
                        move_line_vals = {
                                'name':name,
                                'journal_id':journal_id,
                                'period_id':period_id,
                                'account_id':account_id,
                                'credit':comp_curr_amount,
                                'analytic_account_id':analytic_id,
                                'date':pcl['date'],
                                'ref':pcl['name'],
                                'move_id':move_id,
                                'amount_currency':line2_read['amount'],
                                'currency_id':currency,
                                }
                        if comp_curr_amount > 0:
                            self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                elif line_read['multiple']==False:
                    income_amount+= line_read['amount']
                    comp_curr_amount = line_read['amount'] / rate
                    name = line_read['name']
                    move_line_vals = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':account_id,
                            'credit':comp_curr_amount,
                            'analytic_account_id':analytic_id,
                            'date':pcl['date'],
                            'ref':pcl['name'],
                            'move_id':move_id,
                            'amount_currency':line_read['amount'],
                            'currency_id':currency,
                            }
                    if comp_curr_amount > 0:
                        self.pool.get('account.move.line').create(cr, uid, move_line_vals)
            for line in pcl['pcll_ids']:
                account_id = False
                analytic_id = False
                line_read = self.pool.get('pc.liquidation.lines').read(cr, uid, line, context=None)
                if line_read['account_id']:
                    account_id = line_read['account_id'][0]
                    analytic_id = False
                if line_read['analytic_id']:
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, line_read['analytic_id'][0],context=None)
                    analytic_name = analytic_read['name']
                    analytic_id = analytic_read['id']
                    if not analytic_read['normal_account']:
                        raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
                    if analytic_read['normal_account']:
                        account_id = analytic_read['normal_account'][0]
                if line_read['multiple']==True:
                    for line2 in line_read['pclll_ids']:
                        line2_read = self.pool.get('pc.liquidation.line.lines').read(cr, uid, line2, context=None)
                        expense_amount+= line2_read['amount']
                        comp_curr_amount = line2_read['amount'] / rate
                        name = line_read['name']+' for ' +line2_read['name']
                        move_line_vals = {
                                'name':name,
                                'journal_id':journal_id,
                                'period_id':period_id,
                                'account_id':account_id,
                                'debit':comp_curr_amount,
                                'analytic_account_id':analytic_id,
                                'date':pcl['date'],
                                'ref':pcl['name'],
                                'move_id':move_id,
                                'amount_currency':line2_read['amount'],
                                'currency_id':currency,
                                }
                        if comp_curr_amount > 0:
                            self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                elif line_read['multiple']==False:
                    expense_amount+= line_read['amount']
                    comp_curr_amount = line_read['amount'] / rate
                    name = line_read['name']
                    move_line_vals = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':account_id,
                            'debit':comp_curr_amount,
                            'analytic_account_id':analytic_id,
                            'date':pcl['date'],
                            'ref':pcl['name'],
                            'move_id':move_id,
                            'amount_currency':line_read['amount'],
                            'currency_id':currency,
                            }
                    if comp_curr_amount > 0:
                        self.pool.get('account.move.line').create(cr, uid, move_line_vals)
            pca = self.pool.get('account.pettycash').read(cr, uid, pcl['pc_id'][0],context=None)
            expense_amount = expense_amount / rate
            name = pcl['name'] + " total expense of " + str(expense_amount) 
            move_line_vals = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':pca['account_code'][0],
                        'credit':expense_amount,
                        'date':pcl['date'],
                        'ref':pcl['name'],
                        'move_id':move_id,
                        'amount_currency':pcl['amount'],
                        'currency_id':currency,
                        }
            if expense_amount > 0:
                self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                
            income_amount= income_amount / rate
            name = pcl['name'] + " total income of " + str(income_amount)
            move_line_vals = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':pca['account_code'][0],
                        'debit':income_amount,
                        'date':pcl['date'],
                        'ref':pcl['name'],
                        'move_id':move_id,
                        'amount_currency':pcl['amount'],
                        'currency_id':currency,
                        }
            if income_amount > 0:
                self.pool.get('account.move.line').create(cr, uid, move_line_vals)
                
            self.write(cr, uid, ids, {'state':'completed','move_id':move_id})
            #self.pool.get('account.move').post(cr, uid, )
            self.update_pc(cr, uid, [pcl['id']])
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            check_afterTransactions = self.pool.get('account.pettycash.liquidation').search(cr, uid, [('pc_id','=',pcl['pc_id'][0]),
                                                                                                      ('id','>',pcl['id']),
                                                                                                      ('state','!=','draft')
                                                                                                      ])
            if not check_afterTransactions:
                if pcl['move_id']:
                    move = pcl['move_id'][0]
                    self.pool.get('account.move').button_cancel(cr, uid, [move])
                    self.pool.get('account.move').unlink(cr, uid, [move])
                else: continue
                self.write(cr, uid, ids, {'state':'cancel'})
                self.update_pc_cancel(cr, uid, ids, context)
            elif check_afterTransactions:
                raise osv.except_osv(_('Error !'), _('You can not cancel this transaction because you have created a new transaction for the petty cash account!'))
        return True
    
    def set_to_draft(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, pcl['id'],{'state':'draft'})
        return True
pcl()

class be(osv.osv):
    _inherit = 'bill.exchange'
    _columns = {
        'cash_in':fields.one2many('pettycash.denom','be_id','Cash IN'),
        'cash_out':fields.one2many('pettycash.denom','be_id2','Cash OUT'),
        }
be()