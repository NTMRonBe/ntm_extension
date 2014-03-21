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
import os
import tools

from StringIO import StringIO
import base64

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
        'account_number':fields.char('Account Number',size=32),
        'phone_bill_start':fields.selection([
                                ('01','01'),('02','02'),('03','03'),
                                ('04','04'),('05','05'),('06','06'),
                                ('07','07'),('08','08'),('09','09'),
                                ('10','10'),('11','11'),('12','12'),
                                ('13','13'),('14','14'),('15','15'),
                                ('16','16'),('17','17'),('18','18'),
                                ('19','19'),('20','20'),('21','21'),
                                ('22','22'),('23','23'),('24','24'),
                                ('25','25'),('26','26'),('27','27'),
                                ('28','28'),('29','29'),('30','30'),
                                ('31','31'),
                                    ],'Period Start'),
        'phone_bill_end':fields.selection([
                                ('01','01'),('02','02'),('03','03'),
                                ('04','04'),('05','05'),('06','06'),
                                ('07','07'),('08','08'),('09','09'),
                                ('10','10'),('11','11'),('12','12'),
                                ('13','13'),('14','14'),('15','15'),
                                ('16','16'),('17','17'),('18','18'),
                                ('19','19'),('20','20'),('21','21'),
                                ('22','22'),('23','23'),('24','24'),
                                ('25','25'),('26','26'),('27','27'),
                                ('28','28'),('29','29'),('30','30'),
                                ('31','31'),
                                    ],'Period End'),
        'lt_bool':fields.boolean('Local Tax included?'),
        'it_bool':fields.boolean('International Tax included?'),
        'lt_value':fields.float('Local Tax Rate'),
        'it_value':fields.float('International Tax Rate'),
        'account_id':fields.many2one('account.analytic.account','Phone Account Expense'),
        }
phone_line()

class phone_logs(osv.osv):
    _name = 'phone.logs'
    _description = 'Phone Logs'
    _columns = {
        'name':fields.date('Date'),
        'time':fields.char('Time',size=16),
        'line_id':fields.many2one('phone.line','Phone Line'),
        'extension':fields.char('Extension',size=10),
        'phone_pin':fields.char('Phone Pin',size=10),
        'number':fields.char('Number',size=32),
        'duration':fields.char('Duration',size=32),
        'status':fields.char('Status',size=32),
        'price':fields.float('Log Price'),
        'statement_price':fields.float('Statement Price'),
        'taxed_price':fields.float('Taxed Price'),
        'location':fields.selection([
                            ('local','NDD'),
                            ('international','IDD'),
                            ],'Location'),
        'reconcile':fields.boolean('Reconcile?', readonly=True),
        }
    def reconcile(self, cr, uid, ids,context=None):
        for log in self.read(cr, uid, ids, context=None):
            statement_read = self.pool.get('phone.line').read(cr, uid, log['line_id'][0],context=None)
            tax_included = True
            if statement_read['it_bool'] or statement_read['lt_bool']:
                tax_included = True
            elif not statement_read['it_bool'] and not statement_read['lt_bool']:
                tax_included = False
            taxed = 0.00
            if tax_included ==True:
                taxed = log['statement_price']
                if log['location']==False:
                    raise osv.except_osv(_('Error!'), _('Please change the location!'))
                elif log['location']!=False:
                    self.write(cr, uid,ids, {'reconcile':True, 'taxed_price':taxed})
            elif tax_included==False:
                if log['location']=='local':
                    tax = log['statement_price'] * statement_read['lt_value']
                    taxed = log['statement_price'] * statement_read['lt_value']
                    self.write(cr, uid,ids, {'reconcile':True, 'taxed_price':taxed})
                elif log['location']=='international':
                    taxed = log['statement_price']
                    self.write(cr, uid,ids, {'reconcile':True, 'taxed_price':taxed})
                elif log['location']==False:
                    raise osv.except_osv(_('Error!'), _('Please change the location of the receiving end!'))
        return True                
phone_logs()

class phone_statement(osv.osv):
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'pbd')],limit=1)
        return res and res[0] or False
    
    _name = 'phone.statement'
    _description = "Phone Line Statement of Accounts"
    _columns = {
        'name':fields.char('SOA no.',size=32),
        'due_date':fields.date('Due Date'),
        'line_id':fields.many2one('phone.line','Phone Line'),
        'bill_period':fields.many2one('account.period','Billing Period'),
        'state':fields.selection([
                        ('draft','For Reconciliation'),
                        ('reconciled','For Distribution'),
                        ('distributed','For Payment'),
                        ('paid','Check Clearing'),
                        ('cleared','Check Cleared'),
                        ],'State'),
        'bank_id':fields.many2one('res.partner.bank','Bank Account',domain=[('ownership','=','company')]),
        'amount':fields.float('Total Billed Amount'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'check_number':fields.char('Check Number',size=16),
        'check_date':fields.date('Check Date'),
        'check_amount':fields.float('Check Amount'),
        'distribution_move_id':fields.many2one('account.move','Distribution Entry'),
        'distribution_move_ids': fields.related('distribution_move_id','line_id', type='one2many', relation='account.move.line', string='Distribution Entries', readonly=True),
        'payment_move_id':fields.many2one('account.move','Payment Entry'),
        'payment_move_ids': fields.related('payment_move_id','line_id', type='one2many', relation='account.move.line', string='Payment Entries', readonly=True),
        'clearing_move_id':fields.many2one('account.move','Clearing Entry'),
        'clearing_move_ids': fields.related('clearing_move_id','line_id', type='one2many', relation='account.move.line', string='Clearing Entries', readonly=True),
        }
    _defaults = {
            'state':'draft',
            'journal_id':_get_journal,
            }
phone_statement()
class phone_statement_payment(osv.osv_memory):
    _name = 'phone.statement.payment'
    _description = "Pay Phone Bill Statement"
    _columns = {
        'bank_id':fields.many2one('res.partner.bank','Bank Account',domain=[('ownership','=','company')]),
        'check_amount':fields.float('Check Amount'),
        'check_date':fields.date('Check Date'),
        'check_number':fields.char('Check Number',size=16),
        }
    
    def paybill(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            bank_read = self.pool.get('res.partner.bank').read(cr, uid, form['bank_id'],['journal_id','account_id'])
            statement_read = self.pool.get('phone.statement').read(cr, uid, context['active_id'],context=None)            
            date = datetime.datetime.now()
            date_now = date.strftime("%Y/%m/%d")
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',date_now),('date_stop','>=',date_now)],limit=1)
            journal_id = bank_read['journal_id'][0]
            period_id = period_search[0]
            amount = statement_read['amount']
            move = {
                'journal_id':journal_id,
                'period_id':period_search[0],
                'date':date_now
                }
            move_id = self.pool.get('account.move').create(cr, uid,move)
            user_id = uid
            user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['phone_bill_ap','currency_id','transit_php'])
            move_line = {
                    'name':form['check_number'],
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':company_read['transit_php'][0],
                    'credit':amount,
                    'date':date_now,
                    'ref':statement_read['name'],
                    'move_id':move_id,
                    'amount_currency':amount,
                    'currency_id':company_read['currency_id'][0],
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line = {
                    'name':form['check_number'],
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':company_read['phone_bill_ap'][0],
                    'debit':amount,
                    'date':date_now,
                    'ref':statement_read['name'],
                    'move_id':move_id,
                    'amount_currency':amount,
                    'currency_id':company_read['currency_id'][0],
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            vals_update = {
                    'payment_move_id':move_id,
                    'check_number':form['check_number'],
                    'check_date':form['check_date'],
                    'bank_id':form['bank_id'],
                    'check_amount':amount,
                    'state':'paid',
                    }
            self.pool.get('phone.statement').write(cr, uid, context['active_id'],vals_update)
        return {'type': 'ir.actions.act_window_close'}
        
phone_statement_payment()

class phone_logs_statement(osv.osv):
    _inherit = 'phone.logs'
    _columns = {
        'statement_id':fields.many2one('phone.statement','Statement ID',ondelete='cascade'),
        }
phone_logs_statement()

class phone_statement_distribution(osv.osv):
    _name = 'phone.statement.distribution'
    _description = "Distribution List"
    _columns = {
        'account_id':fields.many2one('account.analytic.account','Account ID'),
        'name': fields.related('account_id','name', type='char',size=64,string='Account Name', readonly=True),
        'phone_pin':fields.many2one('phone.pin','Phone Pin'),
        'amount':fields.float('Charged Amount'),
        'statement_id':fields.many2one('phone.statement','Statement ID', ondelete='cascade'),
        }
phone_statement_distribution()

class phone_statement_additional_wizard(osv.osv_memory):
    _name = 'phone.statement.additional.wizard'
    _description = "Add Additional Charge Wizard"
    _columns = {
        'account_id':fields.many2one('account.analytic.account','Account ID'),
        'description':fields.char('Description',size=64),
        'amount':fields.float('Charged Amount'),
        }
    def add(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=context):
            vals = {
                'account_id':form['account_id'],
                'description':form['description'],
                'amount':form['amount'],
                'statement_id':context['active_id'],
                }
            self.pool.get('phone.statement.additional').create(cr, uid, vals)
        return {'type': 'ir.actions.act_window_close'}
phone_statement_additional_wizard()

class phone_statement_additional(osv.osv):
    _name = 'phone.statement.additional'
    _description = "Additional Charges"
    _columns = {
        'account_id':fields.many2one('account.analytic.account','Account ID'),
        'name': fields.related('account_id','name', type='char',size=64,string='Account Name', readonly=True),
        'description':fields.char('Description',size=64),
        'phone_pin':fields.many2one('phone.pin','Phone Pin'),
        'amount':fields.float('Charged Amount'),
        'statement_id':fields.many2one('phone.statement','Statement ID', ondelete='cascade'),
        }
phone_statement_additional()

class phone_statement_logs(osv.osv):
    _inherit = 'phone.statement'
    _columns = {
        'log_ids':fields.one2many('phone.logs','statement_id','Phone Logs'),
        'distribution_ids':fields.one2many('phone.statement.distribution','statement_id','Distribution Lists'),
        'additional_ids':fields.one2many('phone.statement.additional','statement_id','Additional Charges'),
        'calllogsreconciled':fields.boolean('Call Logs Reconciled'),
        }
    def reconcileLogs(self, cr, uid, ids,context=None):
        for statement in self.read(cr, uid, ids, context=None):
            for log in statement['log_ids']:
                logReader = self.pool.get('phone.logs').read(cr, uid, log, context=None)
                statement_read = self.pool.get('phone.line').read(cr, uid, logReader['line_id'][0],context=None)
                tax_included = True
                if statement_read['it_bool'] or statement_read['lt_bool']:
                    tax_included = True
                elif not statement_read['it_bool'] and not statement_read['lt_bool']:
                    tax_included = False
                taxed = 0.00
                if tax_included ==True:
                    taxed = logReader['statement_price']
                    if logReader['location']==False:
                        raise osv.except_osv(_('Error!'), _('Please change the location!'))
                    elif logReader['location']!=False:
                        self.pool.get('phone.logs').write(cr, uid,log, {'reconcile':True, 'taxed_price':taxed})
                elif tax_included==False:
                    if logReader['location']=='local':
                        tax = logReader['statement_price'] * statement_read['lt_value']
                        taxed = logReader['statement_price'] * statement_read['lt_value']
                        self.pool.get('phone.logs').write(cr, uid,log, {'reconcile':True, 'taxed_price':taxed})
                    elif logReader['location']=='international':
                        taxed = logReader['statement_price']
                        self.pool.get('phone.logs').write(cr, uid,log, {'reconcile':True, 'taxed_price':taxed})
                    elif logReader['location']==False:
                        raise osv.except_osv(_('Error!'), _('Please change the location of the receiving end!'))
            self.write(cr, uid, ids, {'calllogsreconciled':True})
        return True
    
    def reconcile(self, cr, uid, ids, context=None):
        for statement in self.read(cr, uid, ids, context=None):
            log_amount = 0.00
            additional_amount = 0.00
            total_amount = 0.00
            reconciled_logs = self.pool.get('phone.logs').search(cr, uid, [('statement_id','=',statement['id']),('reconcile','=',True)])
            unreconciled_logs = self.pool.get('phone.logs').search(cr, uid, [('statement_id','=',statement['id']),('reconcile','=',False)])
            if unreconciled_logs:
                raise osv.except_osv(_('Error!'), _('All Call logs must be reconciled first before reconciling the statement!'))
            elif not unreconciled_logs:
                for log_id in statement['log_ids']:
                    log_read = self.pool.get('phone.logs').read(cr, uid, log_id,['phone_pin','statement_id','taxed_price'])
                    log_amount+=log_read['taxed_price']
                for additional_id in statement['additional_ids']:
                    additional_read = self.pool.get('phone.statement.additional').read(cr, uid, additional_id, ['amount'])
                    additional_amount +=additional_read['amount']
                total_amount = log_amount + additional_amount
                statement_amount = statement['amount']
                rec_amount = "%.2f" % total_amount
                total_amount = float(rec_amount)
                rec_amount = "%.2f" % statement_amount
                statement_amount = float(rec_amount)
                if statement_amount==total_amount:
                    self.write(cr, uid, ids, {'state':'reconciled'})
                elif statement_amount!=total_amount:
                    total_amount = str(total_amount)
                    statement_amount = str(statement_amount)
                    raise osv.except_osv(_('Error!'), _('Please check the reconciliation! Total amount of call logs and additional charges is not equal to billed amount!'))
        return True
    def distribute(self, cr, uid, ids, context=None):
        for statement in self.read(cr, uid, ids, context=None):
            for log_id in statement['log_ids']:
                log_read = self.pool.get('phone.logs').read(cr, uid, log_id,['phone_pin','statement_id','taxed_price'])
                pin = log_read['phone_pin']
                acc_search = self.pool.get('phone.pin').search(cr, uid, [('name','=',log_read['phone_pin'])])
                if not acc_search:
                    raise osv.except_osv(_('Error!'), _('No account connected to phone pin %s!')%pin)
                elif acc_search:
                    accRead = self.pool.get('phone.pin').read(cr, uid, acc_search[0], ['account_id'])
                    if not accRead['account_id']:
                        raise osv.except_osv(_('Error!'), _('No account connected to phone pin %s!')%pin)
                    acc_id = accRead['account_id'][0]
                    dist_search = self.pool.get('phone.statement.distribution').search(cr, uid, [('statement_id','=',log_read['statement_id'][0]),
                                                                                                 ('account_id','=',acc_id)])
                    if not dist_search:
                        vals = {
                            'phone_pin':acc_search[0],
                            'account_id':acc_id,
                            'amount':log_read['taxed_price'],
                            'statement_id':statement['id'],
                            }
                        self.pool.get('phone.statement.distribution').create(cr, uid, vals)
                    elif dist_search:
                        dist_id = dist_search[0]
                        dist_read = self.pool.get('phone.statement.distribution').read(cr, uid, dist_id,['amount'])
                        new_amt = dist_read['amount']+log_read['taxed_price']
                        self.pool.get('phone.statement.distribution').write(cr, uid, dist_id,{'amount':new_amt})
            self.distribute_entries(cr, uid, ids)
            self.write(cr, uid, ids, {'state':'distributed'})
        return True
                
    def distribute_entries(self, cr, uid, ids, context=None):
        for statement in self.read(cr, uid, ids, context=None):
            date = datetime.datetime.now()
            journal_id = statement['journal_id'][0]
            period_id = statement['bill_period'][0]
            date_now = date.strftime("%Y/%m/%d")
            amount = statement['amount']
            move = {
                'journal_id':statement['journal_id'][0],
                'period_id':period_id,
                'date':date_now
                }
            move_id = self.pool.get('account.move').create(cr, uid,move)
            user_id = uid
            user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['phone_bill_ap','currency_id'])
            move_line = {
                    'name':statement['name'],
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':company_read['phone_bill_ap'][0],
                    'credit':amount,
                    'date':date_now,
                    'ref':statement['name'],
                    'move_id':move_id,
                    'amount_currency':amount,
                    'currency_id':company_read['currency_id'][0],
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            for distribution in statement['distribution_ids']:
                dist_read = self.pool.get('phone.statement.distribution').read(cr, uid, distribution, context=None)
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, dist_read['account_id'][0],['normal_account'])
                name = 'Phone Charges from '+statement['name']
                line_amount = dist_read['amount']
                move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':analytic_read['normal_account'][0],
                    'debit':line_amount,
                    'analytic_account_id':dist_read['account_id'][0],
                    'date':date,
                    'ref':statement['name'],
                    'move_id':move_id,
                    'amount_currency':line_amount,
                    'currency_id':company_read['currency_id'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            for additional_charges in statement['additional_ids']:
                dist_read = self.pool.get('phone.statement.additional').read(cr, uid, additional_charges, context=None)
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, dist_read['account_id'][0],['normal_account'])
                name = dist_read['description']
                line_amount = dist_read['amount']
                move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':analytic_read['normal_account'][0],
                    'debit':line_amount,
                    'analytic_account_id':dist_read['account_id'][0],
                    'date':date,
                    'ref':statement['name'],
                    'move_id':move_id,
                    'amount_currency':line_amount,
                    'currency_id':company_read['currency_id'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids,{'distribution_move_id':move_id})
        return True
        
phone_statement_logs()    

class phone_statement_local(osv.osv_memory):
    _name = 'phone.statement.local'
    _description = "Set to Local"
    
    def add(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=context):
            statement = context['active_id']
            for logs in self.pool.get('phone.logs').search(cr, uid, [('statement_id','=',statement)]):
                logRead = self.pool.get('phone.logs').read(cr, uid, logs, context=None)
                if logRead['location']=='international':
                    continue
                if logRead['location']==False:
                    self.pool.get('phone.logs').write(cr, uid, logs, {'location':'local'})
        return {'type': 'ir.actions.act_window_close'}
phone_statement_local()

class callsdbf_reader(osv.osv_memory):
    _name = "callsdbf.reader"
    _description = "DBF Reader"
    _columns = {
        'bill_period':fields.many2one('account.period','Billing Period'),
        'soa':fields.char('SOA',size=32),
        'due_date':fields.date('Due Date'),
        'provider':fields.many2one('phone.provider','Company'),
        'line_id':fields.many2one('phone.line','Phone Line'),
        'calls_file': fields.binary('Calls.dbf file', required=True),
        'state':fields.selection([('init','init'),('done','done')], 'state', readonly=True),
        }
    
    _defaults = {  
        'state': 'init',
    }
    
    def importzip(self, cr, uid, ids, context):
        user = uid
        file= os.path.join('/var/tmp', 'calls.dbf')
        (data,) = self.browse(cr, uid, ids , context=context)
        module_data = data.calls_file
        val = base64.decodestring(module_data)
        fp = open(file,'wb')
        fp.write(val)
        fp.close
        for form in self.read(cr, uid, ids, context=None):
            statement_id = False
            soa=form['soa']
            statement_search = self.pool.get('phone.statement').search(cr, uid, [('bill_period','=',form['bill_period']),
                                                                                 ('line_id','=',form['line_id']),
                                                                                 ('name','=',form['soa']),
                                                                                 ])
            if statement_search:
                raise osv.except_osv(_('Error!'), _('ERR-007: Statement for SOA %s has already been created!')%soa)
            elif not statement_search:
                self.write(cr, uid, ids, {'state':'done'})
            return True
    
    def clean_file(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            statement_id = False
            soa=form['soa']
            statement_search = self.pool.get('phone.statement').search(cr, uid, [('bill_period','=',form['bill_period']),
                                                                                 ('line_id','=',form['line_id']),
                                                                                 ('name','=',form['soa']),
                                                                                 ])
            if statement_search:
                raise osv.except_osv(_('Error!'), _('ERR-007: Statement for SOA %s has already been created!')%soa)
            elif not statement_search:
                statement = {
                    'bill_period':form['bill_period'],
                    'line_id':form['line_id'],
                    'name':form['soa'],
                    'due_date':form['due_date'],
                    }
                statement_id = self.pool.get('phone.statement').create(cr, uid, statement)
            user_id= uid
            line_id = self.pool.get('phone.line').read(cr, uid, form['line_id'],context=None)
            if line_id['monthly_recur']>0:
                newMRF = False
                if line_id['lt_bool']==False:
                    newMRF= line_id['lt_value'] * line_id['monthly_recur']
                elif line_id['lt_bool']==True:
                    newMRF = line_id['monthly_recur']
                mRFValue = self.pool.get('phone.statement.additional').create(cr, uid, {
                    'account_id':line_id['account_id'][0],
                    'description':'Monthly Recurring Charges',
                    'amount':newMRF,
                    'statement_id':statement_id,
                    })
            line_name = line_id['name']
            start_day = line_id['phone_bill_start']
            end_day = line_id['phone_bill_end']
            period_read =self.pool.get('account.period').read(cr, uid, form['bill_period'],context=None)
            period_name = period_read['name']
            period = period_name.split('/')
            end = int(end_day)
            start = int(start_day)
            start_date = False
            end_date = False
            if start > end:
                end_date = str(period[1])+'-'+str(period[0])+'-'+end_day
                prev_period = form['bill_period']-1
                previous = self.pool.get('account.period').read(cr, uid, prev_period, context=None)
                prev_period_name = previous['name']
                prev_period_list = prev_period_name.split('/')
                start_date = str(prev_period_list[1])+'-'+str(prev_period_list[0])+'-'+start_day
            elif end>start:
                start_date = str(period[1])+'-'+str(period[0])+'-'+start_day
                end_date = str(period[1])+'-'+str(period[0])+'-'+end_day
            #ad = tools.config['root_path'].split(",")[-1]
            file= os.path.join('/var/tmp', 'calls')
            table = dbf.Table(file)
            table.open()
            for record in table:
                date = str(record.date)
                co = str(record.co)
                co = co.strip()
                ext = str(record.extension)
                ext = ext.split(' ')
                ext=ext[0]
                act = str(record.account)
                act = act.split(' ')
                act = act[0]
                dialnumber = str(record.number)
                dialnumber = dialnumber.split(' ')
                dialnumber=dialnumber[0]
                sprice = (record.price)
                stat = str(record.status)
                stat = stat.rstrip()
                iduration = str(record.iduration)
                itime = str(record.itime)
                if co==line_name and date >=start_date and date<=end_date:
                    vals = {}
                    if not sprice:
                        sprice = 0.00
                    sprice = str(sprice)
                    sprice = float(sprice)
                    amount = "%.2f" % sprice
                    sprice = float(amount) 
                    if stat not in ['Local','Incoming']:
                        vals = {
                            'name':date,
                            'line_id':form['line_id'],
                            'extension':ext,
                            'phone_pin':act,
                            'number':dialnumber,
                            'duration':iduration,
                            'time':itime,
                            'status':stat,
                            'price':sprice,
                            'statement_id':statement_id,
                            'statement_price':sprice,
                            }
                        if stat=='Globe' or stat=='Sun' or stat=='Smart':
                            vals.update({'location':'local'})
                        self.pool.get('phone.logs').create(cr, uid, vals)
            table.close()
            return {
                'domain': "[('id', 'in', ["+str(statement_id)+"])]",
                'name': 'Phone Statement',
                'view_type':'form',
                'nodestroy': False,
                'target': 'current',
                'view_mode':'tree,form',
                'res_model':'phone.statement',
                'type':'ir.actions.act_window',
                'context':context,}
    
callsdbf_reader()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,