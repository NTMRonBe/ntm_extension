import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class recur_secondary_curr(osv.osv):
    _name = 'recur.secondary.curr'
    _description = "Secondary Currency Recurring Entries"
    _columns = {
        'name':fields.char('Name', size=64, required=True),
        'journal_id':fields.many2one('account.journal','Journal', required=True),
        'date_start': fields.date('Start Date', required=True),
        'period_total': fields.integer('Number of Periods', required=True),
        'period_nbr': fields.integer('Period', required=True),
        'period_type': fields.selection([('day','days'),('month','month'),('year','year'),('bimonthly','bimonthly')], 'Period Type', required=True),
        }
recur_secondary_curr()

class recur_secondary_curr_line(osv.osv):
    _name = 'recur.secondary.curr.line'
    _description = "Recurring Lines"
    _columns = {
        'name':fields.char('Name',size=64, required=True),
        'analytic_bool':fields.boolean('Analytic Account?'),
        'account_id':fields.many2one('account.account','Normal Account'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'recur_id':fields.many2one('recur.secondary.curr','Recurring ID'),
        'debit':fields.float('Debit'),
        'credit':fields.float('Credit'),
        'currency_id':fields.many2one('res.currency', 'Currency'),
        }
recur_secondary_curr_line()

class rsc(osv.osv):
    _inherit = 'recur.secondary.curr'
    _columns = {
        'line_ids':fields.one2many('recur.secondary.curr.line','recur_id', 'Entry Lines')
        }
rsc()