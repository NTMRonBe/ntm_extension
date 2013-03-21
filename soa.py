import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class soa_request(osv.osv):
    _name = 'soa.request'
    _description = "Statement of Account Requests"
    _columns = {
        'name':fields.char('Subject',size=64),
        'email_adds':fields.text('Email Addresses'),
        'email_from':fields.char('Email From',size=64),
        }
    
    def message_new(self, cr, uid, msg, context=None):
        mailgate_pool = self.pool.get('email.server.tools')

        subject = msg.get('subject') or _("No Subject")
        body = msg.get('body')
        msg_from = msg.get('from')

        vals = {
            'name': subject,
            'email_from': msg_from,
            'email_adds': body,
        }
        res = self.create(cr, uid, vals, context)
        return res
soa_request()

class soa(osv.osv):
    _name = 'soa'
    _description = "Statement of Account"
    _columns = {
            'date':fields.date('Date of Statement'),
            'account_number':fields.many2one('account.analytic.account','Account'),
            'account_code':fields.related('account_number','code',type='char',size=64,store=True, string='Code'),
            'period_id':fields.many2one('account.period','Period of Time'),
            'exchange_rate':fields.float('Exchange Rate'),
            'prev_balance':fields.float('Previous Balance'),
            'total_income':fields.float('Total Income'),
            'total_expense':fields.float('Total Expense'),
            'inc_exp':fields.float('Income-Expenses'),
            'end_balance':fields.float('Ending Balance'),
            }
soa()

class soa_line(osv.osv):
    _name = 'soa.line'
    _description = "Statement of Account Details"
    _columns= {
        'date':fields.date('Date'),
        'name':fields.char('Description',size=100),
        'encoder':fields.many2one('res.users','Encoder'),
        'src_curr':fields.many2one('res.currency','SRC'),
        }
soa_line()


class soa_scheduler(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'soa.scheduler'
    _description = 'Statement of Account Generator'
    _columns = {
        'date':fields.date('Generation Date'),
        'period_id':fields.many2one('account.period','Period'),
        }
    _defaults = {
        'date' : lambda *a: time.strftime('%Y-%m-%d'),
        'period_id':_get_period,
        }
    
    def create_statements(self, cr, uid, ids, context=None):
        date = datetime.datetime.now()
        date = date.strftime("%Y-%m-%d")
        netsvc.Logger().notifyChannel("date", netsvc.LOG_INFO, ''+str(date))
        return True 
            #period = form['period_id']
soa_scheduler()