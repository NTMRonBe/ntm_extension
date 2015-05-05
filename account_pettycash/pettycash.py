
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class account_pettycash(osv.osv):
    _name = "account.pettycash"
    _description = "Petty Cash"
    _columns = {
        'name':fields.char('Petty Cash ID', size=64),
        'manager_id':fields.many2one('res.users','Manager', required=True),
        'date':fields.date('Creation Date', required=True),
        'account_code':fields.many2one('account.account','Account', required=True),
        'currency_id':fields.many2one('res.currency','Currency', required=True,),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirm','Confirmed'),
            ('active','Active'),
            ],'Status', readonly=True),
        }
    _defaults = {
            'name':'NEW',
            'state':'draft',
			'date' : lambda *a: time.strftime('%Y-%m-%d'),
            }
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'account.pettycash')
        })
        return super(account_pettycash, self).create(cr, uid, vals, context)
    
    def write(self, cr, uid, ids, vals, context=None):
        res = super(account_pettycash, self).write(cr, uid, ids, vals, context)
        return res
                        
    def on_change_pca(self, cr, uid, ids, account_code=False):
        result = {}
        currency_id=0
        if account_code:
            account = self.pool.get('account.account').browse(cr, uid, account_code)
            if account.currency_id:
                currency_id = account.currency_id.id
            elif not account.currency_id:
                currency_id = account.company_currency_id.id
            result = {'value':{
                    'currency_id':currency_id,
                      }
                }
        return result
        
account_pettycash()

class pettycash_denom(osv.osv):
	_inherit = "pettycash.denom"
	_columns = {
		'pettycash_id':fields.many2one('account.pettycash',"Petty Cash ID", ondelete="cascade"),
		}
pettycash_denom()

class apc(osv.osv):
    
    _inherit = 'account.pettycash'
    _columns = {
    'denomination_ids':fields.one2many('pettycash.denom','pettycash_id','Denominations Breakdown'),
        }
     
    def get_amount(self, cr, uid, ids, context=None):
		amount = 0.00
		for pc in self.browse(cr, uid, ids, context=None):
			for pc_denom in pc.denomination_ids:
				quantity = pc_denom.quantity
				multiplier = pc_denom.name.multiplier
				amount += quantity * multiplier
				self.write(cr, uid, ids, {'amount':amount})
		return True
	
    def fill_denominations(self, cr, uid, ids, context=None):
		pc_denom_pool = self.pool.get('pettycash.denom')
		denominations = self.pool.get('denominations')
		for inv in self.browse(cr, uid, ids):
			inv_id = inv.id
			currency_id=0.00
			if inv.account_code:
				if inv.account_code.currency_id:
					currency_id = inv.account_code.currency_id.id
				elif not inv.account_code.currency_id:
					currency_id = inv.account_code.company_currency_id.id
				query=("""select * from denominations where currency_id=%s"""%(currency_id))
				cr.execute(query)
				for t in cr.dictfetchall():
					denom_id = t['id']
					pc_denominations = {
								'name':denom_id,
								'pettycash_id':inv.id,
								'quantity':0.00
								}
					pc_denom_pool.create(cr, uid, pc_denominations)
			elif not inv.account_code:
				raise osv.except_osv(_('Error !'), _('PCM-001: Please define the petty cash account !'))
		return self.write(cr, uid, ids, {'state': 'confirm'})

    def set_active(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'active'})
                
apc()

class apc_1(osv.osv):
    
    def _compute_amount(self, cr, uid, ids, field, arg, context=None):
        rec = self.browse(cr, uid, ids, context=None)
        result = {}
        for r in rec:
            amount = 0.00
            for denoms in r.denomination_ids:
                amount += denoms.name.multiplier * denoms.quantity
            result[r.id] = amount
        return result
    
    _inherit = 'account.pettycash'
    _columns = {
    'amount': fields.function(_compute_amount, method=True, type='float', string='Total Amount', store=False),
        }
apc_1()