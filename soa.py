import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class soa(osv.osv):
    _name = 'soa'
    _description = "Statement of Account"
    _columns = {
            'date':fields.date('Date of Statement'),
            'account_number':fields.many2one('account.analytic.account','Account'),
            'account_code':fields.related('account_number','code',type='char',size=64,store=True, string='Code'),
            'period_id':fields.many2one('account.period','Period of Time'),
            'exchange_rate':fields.float('Exchange Rate'),
            }
soa()

class soa_summary(osv.osv):
    _name = 'soa_summary'
    _description = "Statement of Account Summary"
    _columns = {
        'prev_balance':fields.float('Prev'),
        }
soa_summary()

class soa_line(osv.osv):
    _name = 'soa.line'
    _description = "Statement of Account Details"
    _columns= {
        'date':fields.date('Date'),
        'name':fields.char('Description',size=100),
        'encoder':fields.many2one('res.users','Encoder'),
        'src_curr':fields.many2one('res.currency','SRC'),
        'php_equiv':fields.float('Peso Equivalent'),
        'usd_equiv':fields.float('US Dollar Equivalent'),
        }
soa_line()