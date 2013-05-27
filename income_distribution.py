import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
import csv
import dbf

class income_distribution_generic(osv.osv):
    _name = 'income.distribution.generic'
    _description = "Generic Income Distribution"
    _columns = {
        'bank_id':fields.many2one('res.partner.bank','Bank Account'),
        'amount':fields.float('Amount to Distribute'),
        'bank_charges':fields.float('Bank Charges'),
        'name':fields.char('ID',size=16),
        'date':fields.date('Date'),
        'move_id':fields.many2one('account.move','Move Name'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        }
income_distribution_generic()

class income_distribution_generic_lines(osv.osv):
    _name = 'income.distribution.generic.lines'
    _description = "Distribution Lines"
    _columns = {
        'idg_id':fields.many2one('income.distribution.generic','Distribution ID', ondelete='cascade'),
        'account_id':fields.many2one('account.analytic.account','Account'),
        'contribute':fields.boolean('Contribute?'),
        'charges':fields.float('Contribution Charges'),
        'amount':fields.float('Amount'),
        }
    
    def onchange_contribute(self, cr, uid, ids, contribute=False,amount=False):
        result = {}
        if contribute and amount:
            charge = (amount * 6.00)/100.00
            result = {'value':{'charges':charge}}
        elif amount:
            charge = (amount * 6.00)/100.00
            result = {'value':{'charges':charge}}
        elif contribute:
            charge = (amount * 6.00)/100.00
            result = {'value':{'charges':charge}}
        elif not contribute:
            result = {'value':{'charges':0.00}}
        return result
    
income_distribution_generic_lines()

class idg(osv.osv):
    _inherit = 'income.distribution.generic'
    _columns = {
        'distribution_ids':fields.one2many('income.distribution.generic.lines','idg_id','Distribution Lines')
        }
idg()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,