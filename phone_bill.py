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
                            ('local','Local'),
                            ('international','International'),
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
                    tax = (log['statement_price'] * log['lt_value'])/100.00
                    taxed = log['statement_price'] + tax
                    self.write(cr, uid,ids, {'reconcile':True, 'taxed_price':taxed})
                elif log['location']=='international':
                    tax = (log['statement_price'] * log['it_value'])/100.00
                    taxed = log['statement_price'] + tax
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
        'line_id':fields.many2one('phone.line','Phone Line'),
        'bill_start':fields.date('Billing Start Date'),
        'bill_end':fields.date('Billing End Date'),
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
            print context
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
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['phone_bill_ap','currency_id'])
            move_line = {
                    'name':form['check_number'],
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':bank_read['account_id'][0],
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
                    'account_id':company_read['account_id'][0],
                    'debit':amount,
                    'date':date_now,
                    'ref':statement_read['name'],
                    'move_id':move_id,
                    'amount_currency':amount,
                    'currency_id':company_read['currency_id'][0],
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            
        return True
        
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
        'phone_pin':fields.related('account_id','phone_pin', type="char",string='Phone Pin',size=12, readonly=True),
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
        'phone_pin':fields.related('account_id','phone_pin', type="char",string='Phone Pin',size=12, readonly=True),
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
        }
    
    def reconcile(self, cr, uid, ids, context=None):
        for statement in self.read(cr, uid,ids, context=None):
            log_amount = 0.00
            additional_amount = 0.00
            total_amount = 0.00
            reconciled_logs = self.pool.get('phone.logs').search(cr, uid, [('statement_id','=',statement['id']),('reconcile','=',True)])
            unreconciled_logs = self.pool.get('phone.logs').search(cr, uid, [('statement_id','=',statement['id']),('reconcile','=',False)])
            if unreconciled_logs:
                raise osv.except_osv(_('Error!'), _('All Call logs must be reconciled first before reconciling the statement!'))
            for log_id in reconciled_logs:
                log_read = self.pool.get('phone.logs').read(cr, uid, log_id,['phone_pin','statement_id','taxed_price'])
                log_amount+=log_read['taxed_price']
            for additional_id in statement['additional_ids']:
                additional_read = self.pool.get('phone.statement.additional').read(cr, uid, additional_id, ['amount'])
                additional_amount +=additional_read['amount']
            total_amount = log_amount + additional_amount
            if statement['amount']!=total_amount:
                raise osv.except_osv(_('Error!'), _('Please check the reconciliation! Total amount of call logs and additional charges is not equal to billed amount!'))
            elif statement['amount']==total_amount:
                self.write(cr, uid, ids, {'state':'reconciled'})
        return True
    def distribute(self, cr, uid, ids, context=None):
        for statement in self.read(cr, uid, ids, context=None):
            for log_id in statement['log_ids']:
                log_read = self.pool.get('phone.logs').read(cr, uid, log_id,['phone_pin','statement_id','taxed_price'])
                acc_search = self.pool.get('account.analytic.account').search(cr, uid, [('phone_pin','=',log_read['phone_pin'])])
                if not acc_search:
                    pin = log_read['phone_pin']
                    raise osv.except_osv(_('Error!'), _('No account connected to phone pin %s!')%pin)
                elif acc_search:
                    acc_id = acc_search[0]
                    dist_search = self.pool.get('phone.statement.distribution').search(cr, uid, [('statement_id','=',log_read['statement_id'][0]),
                                                                                                 ('account_id','=',acc_id)])
                    if not dist_search:
                        vals = {
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
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',statement['bill_start']),('date_stop','>=',statement['bill_end'])],limit=1)
            date = datetime.datetime.now()
            journal_id = statement['journal_id'][0]
            period_id = period_search[0]
            date_now = date.strftime("%Y/%m/%d")
            amount = statement['amount']
            move = {
                'journal_id':statement['journal_id'][0],
                'period_id':period_search[0],
                'date':date_now
                }
            move_id = self.pool.get('account.move').create(cr, uid,move)
            user_id = uid
            user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['phone_bill_ap','currency_id'])
            move_line = {
                    'name':'Phone Bill Payable',
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


class callsdbf_reader(osv.osv_memory):
    _name = "callsdbf.reader"
    _description = "DBF Reader"
    _columns = {
        'bill_start':fields.date('Billing Start Date'),
        'bill_end':fields.date('Billing End Date'),
        'provider':fields.many2one('phone.provider','Company'),
        'line_id':fields.many2one('phone.line','Phone Line'),
        }
    
    def clean_file(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            statement = {
                'bill_start':form['bill_start'],
                'bill_end':form['bill_end'],
                'line_id':form['line_id'],
                }
            statement_id = self.pool.get('phone.statement').create(cr, uid, statement)
            user_id= uid
            line_id = self.pool.get('phone.line').read(cr, uid, form['line_id'],context=None)
            line_name = line_id['name']            
            user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['calls_dbf'])
            table = company_read['calls_dbf']
            table = dbf.Table(table)
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
                stat = stat.split(' ')
                stat=stat[0]
                iduration = str(record.iduration)
                itime = str(record.itime)
                if co==line_name and date >=form['bill_start'] and date<=form['bill_end']:
                    vals = {}
                    sprice = str(sprice)
                    sprice = float(sprice)
                    amount = "%.2f" % sprice
                    sprice = float(amount) 
                    if sprice>0.00:
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
                        print vals
                        if stat=='Globe' or stat=='Sun' or stat=='Smart':
                            vals.update({'location':'local'})
                        self.pool.get('phone.logs').create(cr, uid, vals)
            table.close()
        return {'type': 'ir.actions.act_window_close'}
    
callsdbf_reader()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,