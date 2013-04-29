
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

def _links_get(self, cr, uid, context={}):
    obj = self.pool.get('res.request.link')
    ids = obj.search(cr, uid, [])
    res = obj.read(cr, uid, ids, ['object', 'name'], context)
    return [(r['object'], r['name']) for r in res]

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
        'type':fields.selection([
                        ('messenger','Messenger'),
                        ('missionary','Missionary'),
                        ], 'Type'),
        'denom_filled':fields.boolean('Filled?'),
        'pc_id':fields.many2one('account.pettycash','PC Account'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'amount':fields.float('Total Amount'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirmed','Confirmed'),
            ('completed','Completed'),
            ('cancel','Cancelled'),
            ],'Status', select=True, readonly=True),
        }
    _defaults = {
            'name':'NEW',
            'state':'draft',
            'amount':0.00,
            'period_id':_get_period,
            }

account_pettycash_liquidation()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pcl_id':fields.many2one('account.pettycash.liquidation','Liquidation',ondelete="cascade"),
        }
pettycash_denom()

class pc_liquidation_lines(osv.osv):
 
    _name = 'pc.liquidation.lines'
    _description = "Liquidation Lines"
    _columns = {
        'name':fields.char('Description',size=64),
        'amount':fields.float('Amount'),
        'account_id':fields.reference('Account', selection=_links_get, size=128, states={'closed':[('readonly',True)]}),
        'reference':fields.char('Reference',size=64),
        'pcl_id':fields.many2one('account.pettycash.liquidation','Liquidation',ondelete="cascade"),
        }
pc_liquidation_lines()

class pcl(osv.osv):
    _inherit = "account.pettycash.liquidation"
    _columns = {
        'denom_breakdown':fields.one2many('pettycash.denom','pcl_id','Denominations Breakdown'),
        'pcll_ids':fields.one2many('pc.liquidation.lines','pcl_id','Liquidation Lines'),
        'mpcll_ids':fields.one2many('pc.liquidation.lines','pcl_id','Liquidation Lines'),
        'partner_id':fields.many2one('res.partner','Missionary'),
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
                        values = {
                            'pcl_id':pcl['id'],
                            'name':denoms,
                            }
                        self.pool.get('pettycash.denom').create(cr, uid, values)
                self.write(cr, uid, ids,{'denom_filled':True})
            if not pcl['pc_id']:
                raise osv.except_osv(_('Error !'), _('Please add pettycash account.'))
        return True
    
    def onchange_pettycash(self, cr, uid, ids, pc_id=False):
        result = {}
        ftp_id = False
        if pc_id:
            for p2b in self.read(cr, uid, ids, context=None):
                ftp_id = p2b['id']
                for p2b_denom in p2b['denom_breakdown']:
                    self.pool.get('pettycash.denom').unlink(cr, uid, p2b_denom)
                ptc_read = self.pool.get('account.pettycash').read(cr, uid, pc_id,['currency_id'])
                currency = ptc_read['currency_id'][1]
                denominations = self.pool.get('denominations').search(cr, uid, [('currency_id','=',ptc_read['currency_id'][0])])
                if not denominations:
                    raise osv.except_osv(_('Error !'), _('%s has no available denominations.Please add them!')%currency)
                new_denoms=[]
                if denominations:
                    for denom in denominations:
                        values = {
                            'name':denom,
                            'pcl_id':ftp_id,
                            }
                        denom_new= self.pool.get('pettycash.denom').create(cr, uid, values)
                        new_denoms.append(denom_new)
                result = {'value':{
                        'denom_breakdown':new_denoms,
                          }
                    }
        return result
            
    
    def confirm_pcl(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            denoms = self.pool.get('pettycash.denom').search(cr, uid, [('pcl_id','=',pcl['id'])])
            lines = self.pool.get('pc.liquidation.lines').search(cr, uid, [('pcl_id','=',pcl['id'])])
            denom_sum = 0.00
            lines_sum = 0.00
            if not denoms:
                raise osv.except_osv(_('Error !'), _('You cannot confirm liquidations that have no denomination lines'))
            if not lines:
                raise osv.except_osv(_('Error !'), _('You cannot confirm liquidations that have no liquidation lines'))
            if denoms:
                for denom in denoms:
                    denom_read = self.pool.get('pettycash.denom').read(cr, uid, denom, context=None)
                    if not denom_read['quantity']:
                        raise osv.except_osv(_('Error !'), _('Denomination lines with 0.00 quantity are not allowed'))
                    elif denom_read['quantity']:
                        denom_reader = self.pool.get('denominations').read(cr, uid, denom_read['name'][0],['multiplier'])
                        product = denom_reader['multiplier'] * denom_read['quantity']
                        denom_sum += product
            if lines:
                for line in lines:
                    line_read = self.pool.get('pc.liquidation.lines').read(cr, uid, line, context=None)
                    if line_read['amount']<1.00:
                        raise osv.except_osv(_('Error !'), _('Liquidation lines that is less than or equal to 0.00 are not allowed'))
                    elif line_read['amount']>0.00:
                        lines_sum += line_read['amount']                
            if denom_sum > 0.00 and lines_sum > 0.00:
                self.write(cr, uid, pcl['id'],{'amount':denom_sum})
                check_amount = 0.00
                pc_read = self.pool.get('account.pettycash').read(cr, uid, pcl['pc_id'][0],['amount'])
                pc_amount = pc_read['amount']
                check_amount = pc_read['amount'] - denom_sum
                if lines_sum == check_amount:
                    values = {
                        'state':'confirmed',
                        'name':self.pool.get('ir.sequence').get(cr, uid, 'account.pettycash.liquidation'),
                        }
                    self.write(cr, uid, pcl['id'], values)
                elif lines_sum > check_amount or lines_sum < check_amount:
                    raise osv.except_osv(_('Error !'), _('Sum of all liquidation lines (%s) must be equal to the \npetty cash amount (%s) less the summation of remaining denomination (%s)!')%(lines_sum,pc_amount,denom_sum))
        return True
    
    def update_pc(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            denoms = self.pool.get('pettycash.denom').search(cr, uid, [('pcl_id','=',pcl['id'])])
            netsvc.Logger().notifyChannel("denoms", netsvc.LOG_INFO, ' '+str(denoms))
            denom_ids = []
            for denom in denoms:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, denom, context=None)
                denom_ids.append(denom_read['name'][0])
                netsvc.Logger().notifyChannel("denom_read", netsvc.LOG_INFO, ' '+str(denom_read))
                pc_denoms = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_read['name'][0]),('pettycash_id','=',pcl['pc_id'][0])])
                netsvc.Logger().notifyChannel("pc_denoms", netsvc.LOG_INFO, ' '+str(pc_denoms))
                for pc_denom in pc_denoms:
                    netsvc.Logger().notifyChannel("pc_denoms", netsvc.LOG_INFO, ' '+str(denom_read['quantity']))
                    self.pool.get('pettycash.denom').write(cr, uid,pc_denom,{'quantity':denom_read['quantity']})
            pc_denom_uninclude = self.pool.get('pettycash.denom').search(cr, uid, [('name','not in',denom_ids),('pettycash_id','=',pcl['pc_id'][0])])
            netsvc.Logger().notifyChannel("pc_denom_uninclude", netsvc.LOG_INFO, ' '+str(pc_denom_uninclude))
            for uninclude in pc_denom_uninclude:
                netsvc.Logger().notifyChannel("uninclude", netsvc.LOG_INFO, ' '+str(uninclude))
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
            amount = 0.00
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
            for line in pcl['pcll_ids']:
                line_read = self.pool.get('pc.liquidation.lines').read(cr, uid, line, context=None)
                ref_account = line_read['account_id'].split(',')
                reference_check = self.pool.get(ref_account[0])
                acc_id = int(ref_account[1])
                account = reference_check.read(cr, uid, acc_id, context=None)
                amount += line_read['amount']
                comp_curr_amount = line_read['amount'] / rate  
                #netsvc.Logger().notifyChannel("amount", netsvc.LOG_INFO, ' '+str(amount))
                account_id = 0
                analytic_id = False
                if ref_account[0]=='account.analytic.account':
                    analytic_name = account['name']
                    if not account['normal_account']:
                        raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
                    if account['normal_account']:
                        account_id = account['normal_account'][0]
                        analytic_id = acc_id
                elif ref_account[0]=='account.account':
                    account_id = acc_id
                move_line_vals = {
                        'name':line_read['name'],
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
                self.pool.get('account.move.line').create(cr, uid, move_line_vals)
            pca = self.pool.get('account.pettycash').read(cr, uid, pcl['pc_id'][0],context=None)
            amount = amount / rate
            move_line_vals = {
                        'name':pcl['name'],
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':pca['account_code'][0],
                        'credit':amount,
                        'date':pcl['date'],
                        'ref':pcl['name'],
                        'move_id':move_id,
                        'amount_currency':pcl['amount'],
                        'currency_id':currency,
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line_vals)
            self.write(cr, uid, ids, {'state':'completed','move_id':move_id})
            self.update_pc(cr, uid, [pcl['id']])
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            if pcl['move_id']:
                move = pcl['move_id'][0]
                self.pool.get('account.move').unlink(cr, uid, [move])
            else: continue
        return self.write(cr, uid, ids, {'state':'cancel'})
    
    def set_to_draft(self, cr, uid, ids, context=None):
        for pcl in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, pcl['id'],{'state':'draft'})
        return True
pcl()