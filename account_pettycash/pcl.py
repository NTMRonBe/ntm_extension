
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

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
        'pc_id':fields.many2one('account.pettycash','PC Account'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'amount':fields.float('Total Amount'),
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
'''    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'account.pettycash.liquidation'),
        })
        return super(account_pettycash_liquidation, self).create(cr, uid, vals, context)
   ''' 
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
        'partner_id':fields.many2one('account.analytic.account','Missionary'),
        'reference':fields.char('Reference',size=64),
        'pcl_id':fields.many2one('account.pettycash.liquidation','Liquidation',ondelete="cascade"),
        }
pc_liquidation_lines()

class pcl(osv.osv):
    _inherit = "account.pettycash.liquidation"
    _columns = {
        'denom_breakdown':fields.one2many('pettycash.denom','pcl_id','Denominations Breakdown'),
        'pcll_ids':fields.one2many('pc.liquidation.lines','pcl_id','Liquidation Lines'),
        }
pcl()