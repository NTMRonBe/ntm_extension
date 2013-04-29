import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
import tools
import wizard
from tools.translate import _
import os


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
            subj = request_read['name']
            subj_split = subj.split(':')
            subj_split_period_code = subj_split[1].split(',')
            code = subj_split_period_code[1]
            period = subj_split_period_code[0]
            netsvc.Logger().notifyChannel("subj_split", netsvc.LOG_INFO, ' '+str(subj_split_period_code))
            acc_search = self.pool.get('account.analytic.account').search(cr, uid, [('code','ilike',code)])
            period_search = self.pool.get('account.period').search(cr, uid, [('name','ilike',period)])
            netsvc.Logger().notifyChannel("period_search", netsvc.LOG_INFO, ' '+str(period_search))
            smtp_login = self.pool.get('email_template.account').search(cr, uid, [('smtpuname','ilike','openerp'),('company','=','yes')])
            use_smtp= False
            for smtp in smtp_login:
                use_smtp = smtp
            if not acc_search:
                raise osv.except_osv(_('Error !'), _('There is no existing account with account code %s')%code)
            elif acc_search:
                if not period_search:
                    raise osv.except_osv(_('Error !'), _('Period %s is not existing!')%period)
                elif period_search:
                    for acc in acc_search:
                        for period_id in period_search:
                            check_soa = self.pool.get('account.soa').search(cr, uid, [('account_number','=',acc),('period_id','=',period_id)])
                            if check_soa:
                                for soa_id in check_soa:
                                    smtp_acct = self.pool.get('email_template.account').read(cr, uid, use_smtp,['email_id'])
                                    account_id = use_smtp
                                    subject = 'Re:' + subj
                                    email_to = request_read['email_adds']
                                    values = {
                                            'account_id':account_id,
                                            'email_to':email_to,
                                            'folder':'outbox',
                                            'body_text':'This is a test',
                                            'subject':subject,
                                            'state':'na',
                                            'server_ref':0
                                            }
                                    email_lists = []
                                    email_created = self.pool.get('email_template.mailbox').create(cr, uid, values)
                                    email_lists.append(email_created)
                                    soa_attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','account.soa'),('res_id','=',soa_id)])
                                    netsvc.Logger().notifyChannel("soa_attachments", netsvc.LOG_INFO, ' '+str(soa_attachments))
                                    for soa_attachment in soa_attachments:
                                        query=("""insert into mail_attachments_rel(mail_id,att_id)values(%s,%s)"""%(email_created,soa_attachment))
                                        cr.execute(query)
        return True
            
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
        'debit':fields.float('Income'),
        'credit':fields.float('Expense'),
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
        debit = 0.00
        credit=0.00
        for statement in self.pool.get('account.soa').search(cr, uid, [('period_id.name','=',period)]):
            soa_reader = self.pool.get('account.soa').read(cr, uid, statement, context=None)
            for aal in self.pool.get('account.analytic.line').search(cr, uid, [('account_id','=',soa_reader['account_number'][0]),('move_id.period_id','=',soa_reader['period_id'][0])]):
                aal_read = self.pool.get('account.analytic.line').read(cr, uid, aal, ['date','amount'])
                if aal_read['amount']<0.00:
                    credit = aal_read['amount'] / -1
                if aal_read['amount']>0.00:
                    debit = aal_read['amount']
                aal_check = self.pool.get('account.soa.line').search(cr, uid, [('link_to','=',aal)])
                if not aal_check:
                    values = {
                        'link_to':aal,
                        'soa_id':statement,
                        'date':aal_read['date'],
                        'debit':debit,
                        'credit':credit,
                        }
                    self.pool.get('account.soa.line').create(cr, uid, values)
            self.pool.get('account.soa').write(cr, uid, statement,{'date':date_now})
        return True
    
    def update_details(self, cr, uid, ids, context=None):
        date = datetime.datetime.now()
        period = date.strftime("%m/%Y")
        date_now = date.strftime("%Y/%m/%d %H:%M")
        for statement in self.pool.get('account.soa').search(cr, uid, [('period_id.name','=',period)]):
            soa_read = self.pool.get('account.soa').read(cr, uid, statement, context=None)
            debit = 0.00
            credit = 0.00
            for line in self.pool.get('account.soa.line').search(cr, uid, [('soa_id','=',statement)]):
                line_read = self.pool.get('account.soa.line').read(cr, uid, line,['debit','credit'])
                debit +=line_read['debit']
                credit+=line_read['credit']
            income_expense = debit - credit
            self.pool.get('account.soa').write(cr, uid, statement,{'total_income':debit,'total_expense':credit,'inc_exp':income_expense})
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
    
    def create_soa_attachment(self, cr, uid, ids, context=None):
        root = tools.config['root_path']
        file = ''
        try:
            os.makedirs(root+'/pdfs/')
        except OSError:
            pass
        for soa_read in self.read(cr, uid, ids, context=None):
            rec = soa_read['id']
            attachments = self.pool.get('ir.attachment').search(cr, uid, [('res_model','=','account.soa'),('res_id','=',rec)])
            self.pool.get('ir.attachment').unlink(cr, uid, attachments)
            period = soa_read['period_id'][1]
            netsvc.Logger().notifyChannel("period", netsvc.LOG_INFO, ' '+str(period))
            split_period = period.split('/')
            period = str(split_period[0])+'_'+split_period[1]
            account = soa_read['account_number'][0]
            account_read = self.pool.get('account.analytic.account').read(cr, uid, account,['name','code'])
            file_name = account_read['code'] +'_'+period
            file = root+'/pdfs/'+file_name+'.pdf'
            service = netsvc.LocalService("report.account.soa")
            (result,format) = service.create(cr, uid, [soa_read['id']],{'model':'account.soa'})
            fp = open(file,'w+');
            try:
                fp.write(result);
            finally:
                fp.close();
        return (True, file)
    
    def gen_report(self,cr, uid, ids, context=None):
        date = datetime.datetime.now()
        period = date.strftime("%m/%Y")
        statements = self.pool.get('account.soa').search(cr, uid, [('period_id.name','=',period)])
        self.pool.get('account.soa').create_soa_attachment(cr, uid, statements)
        return True
        
soa_add_line()