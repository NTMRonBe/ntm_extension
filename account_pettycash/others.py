import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class denominations(osv.osv):
    _name = "denominations"
    _description="Denominations"
    _columns = {
        'name':fields.char('Denomination Name',size=64),
        'multiplier':fields.integer('Multiplier'),
        'currency_id':fields.many2one('res.currency','Currency'),
        'sequence':fields.integer('Sequence'),
        }
    _order = "sequence asc"
    
denominations()


class pettycash_denom(osv.osv):
    
    def _compute_amount(self, cr, uid, ids, field, arg, context=None):
        records = self.browse(cr, uid, ids, context=context)
        result = {}
        for r in records:
            amount = r.name.multiplier * r.quantity
            result[r.id] = amount
        return result 
    
    _name = "pettycash.denom"
    _description = "Petty Cash Denomination Breakdown"
    _columns ={
        'name':fields.many2one('denominations','Denomination'),
        'quantity':fields.integer('Quantity'),
        'currency_id': fields.related('name','currency_id', type='many2one', relation='res.currency', string='Currency', readonly=True),
        'amount': fields.function(_compute_amount, method=True, type='float', string='Total Amount', store=False),
        }
    
    def write(self, cr, uid, ids, vals, context=None):
        print context
        if not context or ('be' not in context):
            res = super(pettycash_denom, self).write(cr, uid, ids, vals, context)
            return res
        if 'be' in context:
            print context
            res = super(pettycash_denom, self).write(cr, uid, ids, vals, context)
            return res
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(pettycash_denom, self).create(cr, uid, vals,context)
        return new_id
    
pettycash_denom()