import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
import csv
import dbf

class phone_provider(osv.osv):
    _name = 'phone.provider'
    _description = "Telecommunication Companies"
    _columns = {
        'name':fields.char('Company',size=64),
        }
phone_provider()

class phone_line(osv.osv):
    _name = 'phone.line'
    _description = "Phone Lines"
    _columns = {
        'name':fields.char('Code',size=2),
        'company_id':fields.many2one('phone.provider','Company'),
        'number':fields.char('Phone Number',size=10),
        'monthly_recur':fields.float('Monthly Recurring Charges'),
        'nat_direct_dial':fields.float('National Direct Dial'),
        'int_direct_dial':fields.float('Internation Direct Dial'),
        'account_id':fields.many2one('account.analytic.account','Phone Account Expense'),
        }
phone_line()

class phone_logs(osv.osv):
    _name = 'phone.logs'
    _description = 'Phone Logs'
    _columns = {
        'name':fields.datetime('Date'),
        'line_id':fields.many2one('phone.line','Phone Line'),
        'extension':fields.char('Extension',size=10),
        'phone_pin':fields.char('Phone Pin',size=10),
        'number':fields.char('Number',size=32),
        'duration':fields.char('Duration',size=32),
        'status':fields.char('Status',size=32),
        'price':fields.float('Server Price'),
        'statement_price':fields.float('Statement Price'),
        }
phone_logs()

class phone_statement(osv.osv):
    _name = 'phone.statement'
    _description = "Phone Line Statement of Accounts"
    _columns = {
        'name':fields.char('SOA no.',size=32),
        'line_id':fields.many2one('phone.line','Phone Line'),
        }
phone_statement()

class phone_logs_statement(osv.osv):
    _inherit = 'phone.logs'
    _columns = {
        'statement_id':fields.many2one('phone.statement','Statement ID',ondelete='cascade'),
        }
phone_logs_statement()

class phone_statement_logs(osv.osv):
    _inherit = 'phone.statement'
    _columns = {
        'log_ids':fields.one2many('phone.logs','statement_id','Phone Logs'),
        }
phone_statement_logs()



class callsdbf_reader(osv.osv_memory):
    _name = "callsdbf.reader"
    _description = "DBF Reader"
    
    def clean_file(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            user_id= uid
            user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['calls_dbf'])
            table = company_read['calls_dbf']
            dbf.delete_fields(table,'trunkgroup')
            dbf.delete_fields(table,'tenant')
            dbf.delete_fields(table,'transfer')
            dbf.delete_fields(table,'hand')
            dbf.delete_fields(table,'calltype')
            dbf.delete_fields(table,'trfgroup')
            dbf.delete_fields(table,'zoneid')
            dbf.delete_fields(table,'currencyid')
            dbf.delete_fields(table,'preflen1')
            dbf.delete_fields(table,'preflen2')
            dbf.delete_fields(table,'meterpulse')
            dbf.delete_fields(table,'ringbefore')
            dbf.delete_fields(table,'callerid')
            dbf.delete_fields(table,'callmode')
        return {'type': 'ir.actions.act_window_close'}
    
callsdbf_reader()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,