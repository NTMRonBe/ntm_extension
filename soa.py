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
        'name':fields.related('link_to','name',type='char',size=64,store=True, string='Description'),
        'date':fields.related('move_id','date',type='date',store=True,string="Date"),
        'amount':fields.related('link_to','amount',type='float',store=True, string='Amount'),
        'currency_amount':fields.related('link_to','amount_currency',type='float',store=True, string='Encoding Amount'),
        'link_to':fields.many2one('account.analytic.line','Analytic Line'),
        'move_id':fields.related('link_to','move_id',type='many2one',relation='account.move.line',store=True,string='Move ID'),
        'soa_id':fields.many2one('soa','SOA'),
        }
    _order = 'date asc'
     
soa_line()

class soa_add_line(osv.osv):
    _inherit = 'soa'
    _columns = {
        'line_ids':fields.one2many('soa.line','soa_id','Details')
        }
    def get_lines(self,cr, uid, ids, context=None):
        date = datetime.datetime.now()
        period = date.strftime("%m/%Y")
        for statement in self.pool.get('soa').search(cr, uid, [('period_id.name','=',period)]):
            soa_reader = self.pool.get('soa').read(cr, uid, statement, context=None)
            for aal in self.pool.get('account.analytic.line').search(cr, uid, [('account_id','=',soa_reader['account_number'][0]),('move_id.period_id','=',soa_reader['period_id'][0])]):
                aal_check = self.pool.get('soa.line').search(cr, uid, [('link_to','=',aal)])
                if not aal_check:
                    values = {
                        'link_to':aal,
                        'soa_id':statement,
                        }
                    self.pool.get('soa.line').create(cr, uid, values)
        return True
soa_add_line()