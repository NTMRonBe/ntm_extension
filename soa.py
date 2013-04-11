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
        'name':fields.char('Subject',size=64,help="The subject must be like this format: SOA:03/2013,account_code"),
        'email_adds':fields.text('Email Addresses'),
        'email_from':fields.char('Email From',size=64),
        'generated':fields.boolean('Generated?',readonly=True)
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
    def create_reply(self, cr, uid, ids, context=None):
        for requests in self.pool.get('soa.request').search(cr, uid, [('generated','=',False)]):
            request_read = self.pool.get('soa.request').read(cr, uid, requests, context=None)
            netsvc.Logger().notifyChannel("request_read", netsvc.LOG_INFO, ' '+str(request_read))
            
soa_request()

class account_soa(osv.osv):
    _name = 'account.soa'
    _description = "Statement of Account"
    _columns = {
            'date':fields.datetime('Statement Date'),
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
account_soa()

class account_soa_line(osv.osv):
    _name = 'account.soa.line'
    _description = "Statement of Account Details"
    _columns= {
        'name':fields.related('link_to','name',type='char',size=64,store=True, string='Description'),
        'date':fields.date('Entry Date'),
        'amount':fields.related('link_to','amount',type='float',store=True, string='Amount'),
        'currency_amount':fields.related('link_to','amount_currency',type='float',store=True, string='Encoding Amount'),
        'link_to':fields.many2one('account.analytic.line','Analytic Line', ondelete='cascade'),
        'move_id':fields.related('link_to','move_id',type='many2one',relation='account.move.line',store=True,string='Move ID'),
        'soa_id':fields.many2one('account.soa','SOA'),
        }
    _order = 'date asc'
     
account_soa_line()

class soa_add_line(osv.osv):
    _inherit = 'account.soa'
    _columns = {
        'line_ids':fields.one2many('account.soa.line','soa_id','Details')
        }
    def get_lines(self,cr, uid, ids, context=None):
        date = datetime.datetime.now()
        period = date.strftime("%m/%Y")
        date_now = date.strftime("%Y/%m/%d %H:%M")
        for statement in self.pool.get('account.soa').search(cr, uid, [('period_id.name','=',period)]):
            soa_reader = self.pool.get('account.soa').read(cr, uid, statement, context=None)
            for aal in self.pool.get('account.analytic.line').search(cr, uid, [('account_id','=',soa_reader['account_number'][0]),('move_id.period_id','=',soa_reader['period_id'][0])]):
                aal_read = self.pool.get('account.analytic.line').read(cr, uid, aal, ['date'])
                netsvc.Logger().notifyChannel("aal_read", netsvc.LOG_INFO, ' '+str(aal_read))
                aal_check = self.pool.get('account.soa.line').search(cr, uid, [('link_to','=',aal)])
                if not aal_check:
                    values = {
                        'link_to':aal,
                        'soa_id':statement,
                        'date':aal_read['date']
                        }
                    self.pool.get('account.soa.line').create(cr, uid, values)
            self.pool.get('account.soa').write(cr, uid, statement,{'date':date_now})
        return True
    
    def generate_soa(self, cr, uid, ids, context=None):
        date = datetime.datetime.now()
        period_con = date.strftime("%m/%Y")
        date_now = date.strftime("%Y/%m/%d %H:%M")
        period_id = self.pool.get('account.period').search(cr, uid, [('name','=',period_con)])
        for aa in self.pool.get('account.analytic.account').search(cr, uid, [('report','=','soa')]):
            for period in period_id:
                statement = self.pool.get('account.soa').search(cr, uid, [('period_id','=',period),('account_number','=',aa)])
                if not statement:
                    values = {
                        'date':date_now,
                        'account_number':aa,
                        'period_id':period,
                        }
                    self.pool.get('account.soa').create(cr, uid, values)
        return True
    def data_get(self, cr, uid, ids, context=None):
        datas = {}
        statements = []
        if context is None:
            context = {}
        for data in self.read(cr, uid, ids, ['id']):
            rec = data['id']
            attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','account.soa'),('res_id','=',rec)])
            self.pool.get('ir.attachment').unlink(cr, uid, attachments)
            statements.append(rec)
        netsvc.Logger().notifyChannel("statements", netsvc.LOG_INFO, ' '+str(statements))
        datas = {
            'ids':statements,
            'model':'account.soa',
            'form':data
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.soa',
            'nodestroy':True,
            'datas': datas,
            }
        
    def data_get_print(self, cr, uid, ids, context=None):
        datas = {}
        statements = []
        if context is None:
            context = {}
        for data in self.read(cr, uid, ids, ['id']):
            rec = data['id']
            statements.append(rec)
        netsvc.Logger().notifyChannel("statements", netsvc.LOG_INFO, ' '+str(statements))
        datas = {
            'ids':statements,
            'model':'account.soa',
            'form':data
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.soa',
            'nodestroy':True,
            'datas': datas,
            }
        
    def gen_report(self,cr, uid, ids, context=None):
        date = datetime.datetime.now()
        period = date.strftime("%m/%Y")
        statements = self.pool.get('account.soa').search(cr, uid, [('period_id.name','=',period)])
        self.pool.get('account.soa').data_get_print(cr, uid, statements)
        return True
soa_add_line()