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
        'bank_charge_account':fields.many2one('account.analytic.account','Bank Charge Account'),
        'amount':fields.float('Amount to Distribute'),
        'bank_charges':fields.float('Bank Charges'),
        'name':fields.char('ID',size=16),
        'remarks':fields.text('Remarks'),
        'rdate':fields.date('Received Date'),
        'ddate':fields.date('Distribute Date'),
        'rmove_id':fields.many2one('account.move','Move Name'),
        'rmove_ids': fields.related('rmove_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'dmove_id':fields.many2one('account.move','Move Name'),
        'dmove_ids': fields.related('dmove_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'ref':fields.char('Reference',size=64),
        'state':fields.selection([
                        ('draft','Draft'),
                        ('received','Money Received'),
                        ('distributed','Received Money Distributed'),
                        ('cancelled','Transaction Cancelled'),
                        ],'State')
        }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'income.distribution.generic'),
            })
        return super(income_distribution_generic, self).create(cr, uid, vals, context)
    
    def cancel(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            if form['state']=='draft':
                self.write(cr, uid, ids, {'state':'cancelled'})
            elif form['state']=='received':
                self.pool.get('account.move').button_cancel(cr, uid, [form['rmove_id'][0]])
                self.pool.get('account.move').unlink(cr, uid, [form['rmove_id'][0]])
                self.write(cr, uid, ids, {'state':'cancelled'})
            elif form['state']=='distributed':
                self.pool.get('account.move').unlink(cr, uid, [form['dmove_id'][0]])
                self.write(cr, uid, ids, {'state':'received'})
        return True
    
    def cancelTransaction(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            self.pool.get('account.move').unlink(cr, uid, [form['dmove_id'][0]])
            self.pool.get('account.move').unlink(cr, uid, [form['rmove_id'][0]])
            self.write(cr, uid, ids, {'state':'cancelled'})
        return True
    
    _defaults = {
        'state':'draft',
        'rdate':lambda *a: time.strftime('%Y-%m-%d'),
        'ddate':lambda *a: time.strftime('%Y-%m-%d'),
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
        'remarks':fields.char('Remarks',100),
        }
    
    def onchange_contribute(self, cr, uid, ids, contribute=False,amount=False):
        result = {}
        user_id = uid
        user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
        company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['contribution'])
        contribution = company_read['contribution']
        if contribute and amount:
            charge = (amount * contribution)/100.00
            result = {'value':{'charges':charge}}
        elif amount and contribute==False:
            result = {'value':{'charges':0.00}}
        elif contribute:
            charge = (amount * contribution)/100.00
            result = {'value':{'charges':charge}}
        elif not contribute:
            result = {'value':{'charges':0.00}}
        return result
    
income_distribution_generic_lines()

class idg(osv.osv):
    _inherit = 'income.distribution.generic'
    _columns = {
        'distribution_ids':fields.one2many('income.distribution.generic.lines','idg_id','Distribution Lines'),
        'charges_included':fields.boolean('Charges still included'),
        }
    
    def receive(self, cr, uid, ids, context=None):
        user_id = uid
        user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
        company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['currency_id','donations','bank_charge'])
        comp_curr = company_read['currency_id'][0]
        rate = False
        currency = False
        for idg in self.read(cr, uid, ids, context=None):
            bank_read = self.pool.get('res.partner.bank').read(cr, uid, idg['bank_id'][0],['currency_id','journal_id','account_id'])
            journal_id = bank_read['journal_id'][0]
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',idg['rdate']),('date_stop','>=',idg['rdate'])],limit=1)
            period_id = period_search[0]
            if bank_read['currency_id'][0]!=comp_curr:
                curr_read = self.pool.get('res.currency').read(cr, uid, bank_read['currency_id'][0],['rate'])
                currency = bank_read['currency_id'][0]
                rate = curr_read['rate']
            elif bank_read['currency_id'][0]==comp_curr:
                currency= bank_read['currency_id'][0]
                rate = 1.00
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':idg['rdate'],
                'ref':idg['name'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            amount = idg['amount'] / rate
            name = "Donation with reference #" + idg['ref']
            move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':company_read['donations'][0],
                    'credit':amount,
                    'date':idg['rdate'],
                    'ref':idg['name'],
                    'move_id':move_id,
                    'amount_currency':idg['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            donated_amt = False
            charge_amt = False
            if not idg['charges_included']:
                donated_amt = idg['amount']
            elif idg['charges_included']:
                bankChargeAccount = self.pool.get('account.analytic.account').read(cr, uid, idg['bank_charge_account'][0], ['normal_account'])
                if idg['bank_charges']<=0.00:
                    raise osv.except_osv(_('IDG-001!'), _('ERROR CODE - IDG-001: If Charges are still included, bank charges must be greater than 0.00!'))
                elif idg['bank_charges']>0.00:
                        donated_amt = idg['amount'] - idg['bank_charges']
                        charge_amt = idg['bank_charges']
                        amount = charge_amt / rate
                        name = "Charges for donation with reference #" + idg['ref']
                        move_line = {
                                'name':name,
                                'journal_id':journal_id,
                                'period_id':period_id,
                                'account_id':bankChargeAccount['normal_account'][0],
                                'debit':amount,
                                'date':idg['rdate'],
                                'ref':idg['name'],
                                'move_id':move_id,
                                'analytic_account_id':idg['bank_charge_account'][0],
                                'amount_currency':charge_amt,
                                'currency_id':currency,
                                }
                        self.pool.get('account.move.line').create(cr, uid, move_line)
            amount = donated_amt / rate
            name = "Received donations with reference #" + idg['ref']
            move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':bank_read['account_id'][0],
                    'debit':amount,
                    'date':idg['rdate'],
                    'ref':idg['name'],
                    'move_id':move_id,
                    'amount_currency':donated_amt,
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)    
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'rmove_id':move_id,'state':'received'})
        return True
    
    def receive2(self, cr, uid, ids, context=None):
        print context
        return True
    
    
    def distribute(self, cr, uid, ids, context=None):
        user_id = uid
        user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
        company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['currency_id','contributions_acct','donations','bank_charge'])
        comp_curr = company_read['currency_id'][0]
        rate = False
        currency = False
        for idg in self.read(cr, uid, ids, context=None):
            bank_read = self.pool.get('res.partner.bank').read(cr, uid, idg['bank_id'][0],['currency_id','journal_id','account_id'])
            journal_id = bank_read['journal_id'][0]
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',idg['ddate']),('date_stop','>=',idg['ddate'])],limit=1)
            period_id = period_search[0]
            if bank_read['currency_id'][0]!=comp_curr:
                curr_read = self.pool.get('res.currency').read(cr, uid, bank_read['currency_id'][0],['rate'])
                currency = bank_read['currency_id'][0]
                rate = curr_read['rate']
            elif bank_read['currency_id'][0]==comp_curr:
                currency= bank_read['currency_id'][0]
                rate = 1.00
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':idg['ddate'],
                'ref':idg['name'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            total_distribution = False
            total_contribution = False
            curr_distribution = False
            curr_contribution = False
            if idg['distribution_ids']==[]:
                raise osv.except_osv(_('Error!'), _('ERROR CODE - IDG-002: You must have a distribution list before distribution!'))
            elif idg['distribution_ids']!=[]:
                for idgl in idg['distribution_ids']:
                    idgl_read = self.pool.get('income.distribution.generic.lines').read(cr, uid, idgl, context=None)
                    account_read = self.pool.get('account.analytic.account').read(cr, uid, idgl_read['account_id'][0],['normal_account'])
                    distribution_amt = idgl_read['amount'] / rate
                    contribution = idgl_read['charges'] / rate
                    amount = "%.3f" % distribution_amt
                    distribution_amt = float(amount)
                    curr_distribution +=distribution_amt
                    amount = "%.3f" % contribution
                    contribution = float(amount)
                    curr_contribution +=contribution                
                    total_distribution += idgl_read['amount']
                    total_contribution += idgl_read['charges']
                    name = "Distribution for "+idgl_read['remarks'] +" with reference#" + idg['ref']
                    move_line = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':account_read['normal_account'][0],
                            'credit':distribution_amt,                        
                            'date':idg['ddate'],
                            'ref':idg['name'],
                            'move_id':move_id,
                            'analytic_account_id':idgl_read['account_id'][0],
                            'amount_currency':idgl_read['amount'],
                            'currency_id':currency,
                            }
                    self.pool.get('account.move.line').create(cr, uid, move_line)
                    if contribution!=0.00:
                        name = "Contribution of " + idgl_read['remarks'] + " with reference#" + idg['ref']
                        move_line = {
                                'name':name,
                                'journal_id':journal_id,
                                'period_id':period_id,
                                'account_id':account_read['normal_account'][0],
                                'debit':contribution,                        
                                'date':idg['ddate'],
                                'ref':idg['name'],
                                'move_id':move_id,
                                'analytic_account_id':idgl_read['account_id'][0],
                                'amount_currency':idgl_read['charges'],
                                'currency_id':currency,
                                }
                        self.pool.get('account.move.line').create(cr, uid, move_line)
                    idg_amount = idg['amount']
                    idg_amount = "%.3f" % idg_amount
                    idg_amount = float(idg_amount)
                    total_distribution = "%.3f" % total_distribution
                    total_distribution = float(total_distribution)
                    if total_distribution != idg_amount:
                        raise osv.except_osv(_('Error!'), _('ERROR CODE - IDG-003: Total received amount is not equal to the total amount to be distributed!'))
                    elif total_distribution== idg['amount']:
                        name = "Total Distributed Amount with ref#" + idg['ref']
                        move_line = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':company_read['donations'][0],
                            'debit':curr_distribution,                        
                            'date':idg['ddate'],
                            'ref':idg['name'],
                            'move_id':move_id,
                            'amount_currency':total_distribution,
                            'currency_id':currency,
                            }
                        self.pool.get('account.move.line').create(cr, uid, move_line)
                    if curr_contribution!=0.00:
                        name = "Total Contributed Amount with ref#" + idg['ref']
                        move_line = {
                               'name':name,
                               'journal_id':journal_id,
                               'period_id':period_id,
                               'account_id':company_read['contributions_acct'][0],
                               'credit':curr_contribution,                        
                               'date':idg['ddate'],
                               'ref':idg['name'],
                               'move_id':move_id,
                               'amount_currency':total_contribution,
                               'currency_id':currency,
                            }
                        self.pool.get('account.move.line').create(cr, uid, move_line)
                    self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'state':'distributed','dmove_id':move_id})
        return True
idg()


class voucher_distribution(osv.osv):
    
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'vd')],limit=1)
        return res and res[0] or False
    
    _name = 'voucher.distribution'
    _description = "US and Canada Voucher Distribution"
    _columns ={
        'name':fields.char('Description',size=100),
        'date':fields.date('Date'),
        'rdate':fields.date('Receiving Date'),
        'vd_holder':fields.many2one('account.account','Voucher Account'),
        'wire_fee':fields.float('US Wire Fee'),
        'money_received':fields.float('Money Received'),
        'wire_fee_account':fields.many2one('account.analytic.account','Wire Fee Expense Account'),
        'country':fields.many2one('res.country','Country',domain=[('code','in',['US','CA'])],required=True),
        'period_id':fields.many2one('account.period','Period'),
        'rperiod_id':fields.many2one('account.period','Period'),
        'bank_id':fields.many2one('res.partner.bank','Bank'),
        'rremarks':fields.char('Remarks', size=100),
        'generated':fields.boolean('Generated'),
        'journal_id':fields.many2one('account.journal','Journal ID'),
        'missionary_subtotal':fields.float('Missionary Account Subtotal',digits_compute=dp.get_precision('Account')),
        'recovery_charges':fields.float('Recovery Charges',digits_compute=dp.get_precision('Account')),
        'natw_total_charges':fields.float('N@W Charges',digits_compute=dp.get_precision('Account')),
        'postage_recovery':fields.float('Postage Recovery Expense',digits_compute=dp.get_precision('Account')),
        'envelope_recovery':fields.float('Envelope Recovery Expense',digits_compute=dp.get_precision('Account')),
        'currency_id':fields.many2one('res.currency','Currency', required=True),
        'state':fields.selection([('draft','Draft'),
                                  ('received','Received'),
                                  ('generated','Generated'),
                                  ('distributed','Voucher Distributed'),
                                  ('entry_created','Distribution Done')],'State'),
        'm_move_id':fields.many2one('account.move','Missionary Entries'),
        'm_move_ids': fields.related('m_move_id','line_id', type='one2many', relation='account.move.line', string='Missionary Entries', readonly=True),
        'r_move_id':fields.many2one('account.move','Receiving Entries'),
        'r_move_ids': fields.related('r_move_id','line_id', type='one2many', relation='account.move.line', string='Receiving Entries', readonly=True),
        }
    _defaults = {
            'date': lambda *a: time.strftime('%Y-%m-%d'),
            'state':'draft',
            'journal_id':_get_journal,
            'rdate': lambda *a: time.strftime('%Y-%m-%d'),
            }
    
    def create(self, cr, uid, vals, context):
        period_read = self.pool.get('account.period').read(cr, uid, vals['period_id'],['name'])
        country_read = self.pool.get('res.country').read(cr, uid, vals['country'],['code'])
        name = country_read['code']+' Voucher as of '+ period_read['name']
        vals.update({
                'name': name
                })
        return super(voucher_distribution, self).create(cr, uid, vals, context)
    
    def receive(self, cr, uid, ids, context=None):
        for vd in self.read(cr, uid, ids, context=None):
            bankRead = self.pool.get('res.partner.bank').read(cr, uid, vd['bank_id'][0], context=None)
            period_id = vd['rperiod_id'][0]
            date = vd['rdate']
            journal_id = bankRead['journal_id'][0]
            bankAcct = bankRead['account_id'][0]
            currRead = self.pool.get('res.currency').read(cr, uid, vd['currency_id'][0], context=None)
            wireAccRead = self.pool.get('account.analytic.account').read(cr, uid, vd['wire_fee_account'][0], ['normal_account'])
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date,
                'ref':vd['rremarks'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            name = 'Total Amount transferred to Bank'
            transferred_curr= vd['money_received'] + vd['wire_fee']
            transferred_comp_curr = transferred_curr / currRead['rate']
            amount = "%.2f" % transferred_comp_curr
            transferred_comp_curr = float(amount)
            move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':vd['vd_holder'][0],
                        'credit':transferred_comp_curr,                        
                        'date':date,
                        'ref':vd['rremarks'],
                        'move_id':move_id,
                        'amount_currency':transferred_curr,
                        'currency_id':vd['currency_id'][0],
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            name = 'Bank Fee - '+ vd['rremarks']
            transferred_curr= + vd['wire_fee']
            transferred_comp_curr = transferred_curr / currRead['rate']
            amount = "%.2f" % transferred_comp_curr
            transferred_comp_curr = float(amount)
            move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':wireAccRead['normal_account'][0],
                        'debit':transferred_comp_curr,                        
                        'date':date,
                        'ref':vd['rremarks'],
                        'move_id':move_id,
                        'analytic_account_id':vd['wire_fee_account'][0],
                        'amount_currency':transferred_curr,
                        'currency_id':vd['currency_id'][0],
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            name = 'Money Received - '+ vd['rremarks']
            transferred_curr= + vd['money_received']
            transferred_comp_curr = transferred_curr / currRead['rate']
            amount = "%.2f" % transferred_comp_curr
            transferred_comp_curr = float(amount)
            move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':bankAcct,
                        'debit':transferred_comp_curr,                        
                        'date':date,
                        'ref':vd['rremarks'],
                        'move_id':move_id,
                        'amount_currency':transferred_curr,
                        'currency_id':vd['currency_id'][0],
                        }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.write(cr, uid, ids, {'state':'received','r_move_id':move_id})
voucher_distribution()

class voucher_distribution_line(osv.osv):
    _name = 'voucher.distribution.line'
    _description = "Voucher Distribution Lines"
    _columns = {
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade'),
        'name':fields.char('Description',size=100),
        'comments':fields.char('Comments',size=100),
        'co1':fields.char('CO1',size=10),
        'batch_date':fields.date('Batch Date'),
        'included_in_charged':fields.boolean('Included in Charging', readonly=True),
        'co2':fields.char('CO2',size=10),
        'doc_num':fields.char('DOC No',size=10),
        'code':fields.char('CODE',size=10),
        'amount':fields.float('Amount'),
        'donorname':fields.char('Donor Name', size=64),
        'dcno':fields.char('DC No',size=32),
        'city':fields.char('City', size=64),
        'addr2':fields.char('Address', size=100),
        'state':fields.char('State/Province',size=32),
        'account_name':fields.char('Account Name',size=100),
        'analytic_account_id':fields.many2one('account.analytic.account','Analytic Account'),
        'account_id':fields.many2one('account.account','Normal Account'),
        'type':fields.selection([
                        ('mission','Missionary'),
                        ('personal','Personal'),
                        ('voucher','Voucher'),
                        ('other','Other'),
                        ],'Type'),
        }
    _order = 'account_name desc'
    
    def onchange_accountid(self, cr, uid, ids, account_id):
        res = {}
        if account_id:
            accountRead = self.pool.get('account.account').read(cr, uid, account_id, ['name'])
            res = {'value':{'account_id':account_id,'account_name':accountRead['name'], 'analytic_account_id':False}}
        elif not account_id:
            res = {'value':{'account_id':False,'account_name':False, 'analytic_account_id':False}}
        return res
    
    def onchange_analyticid(self, cr, uid, ids, analytic_account_id):
        res = {}
        if analytic_account_id:
            accountRead = self.pool.get('account.analytic.account').read(cr, uid, analytic_account_id, ['name'])
            res = {'value':{'analytic_account_id':analytic_account_id,'account_name':accountRead['name'], 'account_id':False}}
        elif not analytic_account_id:
            res = {'value':{'account_id':False,'account_name':False, 'analytic_account_id':False}}
        return res
    
voucher_distribution_line()

class voucher_distribution_personal_section(osv.osv):
    _name = 'voucher.distribution.personal.section'
    _description = "Personal Account Section"
    _columns = {
        'name':fields.char('Description',size=64),
        'amount':fields.float('Amount'),
        'account_name':fields.char('Account Name',size=64),
        'account_id':fields.many2one('account.account','Normal Account'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade'),
        'transaction_code':fields.selection([
                                    ('dp','Deposits to Personal'),
                                    ('pd','Personal Disbursements'),
                                    ('v','Voucher'),
                                    ]),
        }
    
    _order = 'amount asc'
    
    def onchange_accountid(self, cr, uid, ids, account_id):
        res = {}
        if account_id:
            accountRead = self.pool.get('account.account').read(cr, uid, account_id, ['name'])
            res = {'value':{'account_id':account_id,'account_name':accountRead['name'], 'analytic_id':False}}
        elif not account_id:
            res = {'value':{'account_id':False,'account_name':False, 'analytic_id':False}}
        return res
    
    def onchange_analyticid(self, cr, uid, ids, analytic_id):
        res = {}
        if analytic_id:
            accountRead = self.pool.get('account.analytic.account').read(cr, uid, analytic_id, ['name'])
            res = {'value':{'analytic_id':analytic_id,'account_name':accountRead['name'], 'account_id':False}}
        elif not analytic_id:
            res = {'value':{'analytic_id':False,'account_name':False, 'account_id':False}}
        return res
voucher_distribution_personal_section()

class voucher_distribution_email_charging(osv.osv):
    _name = 'voucher.distribution.email.charging'
    _description = "Email Charging"
    _columns = {
        'name':fields.char('Email Account Description',size=64, required=True),
        'amount':fields.float('Amount'),
        'account_id':fields.many2one('account.analytic.account','Analytic Account'),
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade'),
        }
voucher_distribution_email_charging()


class email_charging_account(osv.osv):
    _name = 'email.charging.account'
    _description = "Email Charging Account Configuration"
    _columns = {
        'name':fields.char('Email Account (Voucher)',size=64, required=True),
        'description':fields.char('Description',size=64, required=True),
        'account_id':fields.many2one('account.analytic.account','Analytic Account', required=True)
        }
email_charging_account()

class voucher_distribution_natw_charge(osv.osv):
    _name = 'voucher.distribution.natw.charge'
    _description = "N@W Charges"
    _columns = {
        'name':fields.char('Charged For',size=64),
        'amount':fields.float('Amount'),
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade'),
        }
voucher_distribution_natw_charge()

class voucher_distribution_account_charging(osv.osv):
    _name = 'voucher.distribution.account.charging'
    _description = "Voucher Distribution Account Charging"
    _columns = {
        'name':fields.char('Account Name',size=64),
        'code':fields.char('Account ID',size=64),
        'account_id':fields.many2one('account.analytic.account','Account Charged'),
        'contingency':fields.float('Contingency Charges'),
        'postage':fields.float('Postage/Env Recovery'),
        'natw':fields.float('N@W Charges'),
        'extra':fields.float('Extra Charges'),
        'total':fields.float('Total'),
        'entries_amount':fields.float('Entries Amount'),
        'total_entries':fields.integer('No of Entries'),
        'charged':fields.boolean('Charged',readonly=True),
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade'),
        }
voucher_distribution_account_charging()

class voucher_distribution_9phna(osv.osv):
    _name = 'voucher.distribution.missionaries'
    _description = "Missionary Charging"
    _columns = {
        'name':fields.char('Name',size=64, required=True),
        'account_id':fields.many2one('account.analytic.account','Account Name', required=True),
        'national':fields.boolean('Philippine National'),
        }
voucher_distribution_9phna()

class voucher_distribution_voucher_transfer(osv.osv):
    _name = 'voucher.distribution.voucher.transfer'
    _description = "Voucher Transfer"
    _columns = {
        'name':fields.char('Description',size=64),
        'comment':fields.char('Comments',size=64),
        'amount':fields.float('Amount',digits_compute=dp.get_precision('Account')),
        'account_name':fields.char('`Account Name',size=100),
        'analytic_account_id':fields.many2one('account.analytic.account','Analytic Account'),
        'account_id':fields.many2one('account.account','Normal Account'),
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade'),
        }
    _order = 'name asc, comment asc'
    
    def onchange_account(self, cr, uid, ids,  account_id):
        res = {}
        if account_id:
            acc_read = self.pool.get('account.account').read(cr, uid, account_id, ['name'])
            res = {'value':{'account_name':acc_read['name']}}
        elif account_id==False:
            res = {'value':{'account_name':False}}
        return res
    
    def onchange_analytic(self, cr, uid, ids,analytic_account_id):
        res = {}
        if analytic_account_id:
            acc_read = self.pool.get('account.analytic.account').read(cr, uid, analytic_account_id, ['name'])
            res = {'value':{'account_name':acc_read['name']}}
        elif analytic_account_id==False:
            res = {'value':{'account_name':False}}
        return res
voucher_distribution_voucher_transfer()

class vd(osv.osv):
    _inherit = 'voucher.distribution'
    _columns = {
        'natw_charges':fields.one2many('voucher.distribution.natw.charge','voucher_id','NTM at Work Charges'),
        'charging_lines':fields.one2many('voucher.distribution.account.charging','voucher_id','Charging Lines'),
        'voucher_lines':fields.one2many('voucher.distribution.line','voucher_id','Voucher Lines'),
        'email_charges':fields.one2many('voucher.distribution.email.charging','voucher_id','Email Charges'),
        'dp_section':fields.one2many('voucher.distribution.personal.section','voucher_id','Deposits to Personal',domain=[('transaction_code','=','dp')]),
        'pdv_section':fields.one2many('voucher.distribution.personal.section','voucher_id','Personal Disbursements and Vouchers',domain=[('transaction_code','!=','dp')]),
        'voucher_transfer_lines':fields.one2many('voucher.distribution.voucher.transfer','voucher_id','Voucher Transfers'),
        'total_gifts':fields.float('Total Gifts', readonly=True),
        'autocontribution':fields.float('Automatic Contribution', readonly=True),
        'postage_ratio':fields.float('Postage Ratio',readonly=True,digits=(16,8)),
        'contingency_ratio':fields.float('Contingency Ratio', readonly=True,digits=(16,8)),
        'natw_ratio':fields.float('N@W Ratio',readonly=True,digits=(16,8)),
        'extra_ratio':fields.float('Extra Charges', readonly=True,digits=(16,8))
        }
    def check_accounts(self, cr, uid, ids, context=None):
        phna_pool = []
        phna_idpool = []
        phna_accs = self.pool.get('voucher.distribution.missionaries').search(cr, uid, [])
        for phna in phna_accs:
            phna_read = self.pool.get('voucher.distribution.missionaries').read(cr, uid, phna,context=None)
            phna_name = phna_read['name']
            phna_name = phna_name.replace(' ','')
            phna_name = phna_name.replace('&','')
            phna_name = phna_name.lower()
            phna_pool.append(phna_name)
            phna_idpool.append(phna_read['id'])
        for vd in self.read(cr, uid, ids, context=None):
            for vdl in vd['voucher_lines']:
                vdlread= self.pool.get('voucher.distribution.line').read(cr, uid, vdl, context=None)
                vdlread_description = vdlread['name']
                vdlread_comments = vdlread['comments']
                vdlread_code=vdlread['code']
                vdlread_code = vdlread_code.replace(' ','')
                vdlread_code = vdlread_code.lower()
                if 'N@W' in vdlread_description:
                    vals = {
                        'name':vdlread['comments'],
                        'voucher_id':vd['id'],
                        'amount':vdlread['amount'],
                        }
                    self.pool.get('voucher.distribution.natw.charge').create(cr, uid, vals)
                    self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
                    vdread = self.read(cr, uid, vd['id'],['natw_total_charges'])
                    recover =vdread['natw_total_charges']+vdlread['amount']
                    self.write(cr, uid, vd['id'], {'natw_total_charges':recover})
                elif 'POSTAGE' in vdlread_description:
                    self.write(cr, uid, vd['id'], {'postage_recovery':vdlread['amount']})
                    vdread = self.read(cr, uid, vd['id'],['recovery_charges'])
                    recover =vdread['recovery_charges']+vdlread['amount']
                    self.write(cr, uid, vd['id'], {'recovery_charges':recover})
                    self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
                elif 'ENV' in vdlread_description:
                    self.write(cr, uid, vd['id'], {'envelope_recovery':vdlread['amount']})
                    vdread = self.read(cr, uid, vd['id'],['recovery_charges'])
                    recover =vdread['recovery_charges']+vdlread['amount']
                    self.write(cr, uid, vd['id'], {'recovery_charges':recover})
                    self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
                elif 'EMAIL' in vdlread_description:
                    vdlread_comments = vdlread_comments.replace('USER: ','')
                    vdlread_comments = vdlread_comments.replace(' ','')
                    email_search = self.pool.get('email.charging.account').search(cr, uid, [('name','=',vdlread_comments)], limit=1)
                    if email_search:
                        email_read = self.pool.get('email.charging.account').read(cr, uid, email_search[0], context=None)
                        check_emailcharging = self.pool.get('voucher.distribution.email.charging').search(cr, uid, [('name','=',email_read['description'])])
                        if check_emailcharging:
                            charging_read = self.pool.get('voucher.distribution.email.charging').read(cr, uid, check_emailcharging[0],['amount'])
                            charging_amount = charging_read['amount']+ vdlread['amount']
                            self.pool.get('voucher.distribution.email.charging').write(cr, uid, check_emailcharging[0],{'amount':charging_amount})
                        elif not check_emailcharging:
                            vals = {
                                'name':email_read['description'],
                                'voucher_id':vd['id'],
                                'amount':vdlread['amount'],
                                }
                            if email_read['account_id']:
                                vals.update({'account_id':email_read['account_id'][0]})
                            self.pool.get('voucher.distribution.email.charging').create(cr, uid, vals)
                    self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
                else:
                    vdlread_description = vdlread_description.lower()
                    if vdlread['type']=='personal':
                        vdlread_code = vdlread['code'].lower()
                        name = vdlread['name']+'\n\n'+vdlread['comments']
                        personal_vals = {
                                    'name':name,
                                    'voucher_id':vd['id'],
                                    'amount':vdlread['amount'],
                                    'transaction_code':vdlread_code,
                                    }
                        self.pool.get('voucher.distribution.personal.section').create(cr, uid, personal_vals)
                        self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
                    #if vdlread_code=='md':
                    ##    uncharged_vals = {
                    #            'name':vdlread['name'],
                    #            'amount':vdlread['amount'],
                    #            'voucher_id':vd['id'],
                    #            }
                    #    self.pool.get('voucher.distribution.uncharged').create(cr, uid, uncharged_vals)
                    #    self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
                    if vdlread['type']=='voucher':
                        vdlread_description = vdlread_description.replace(' ','')
                        vdlread_description = vdlread_description.replace('&','')
                        ctr = 0
                        if vdlread_description in phna_pool:
                            for phna_pool_name in phna_pool:
                                if phna_pool_name!=vdlread_description:
                                    ctr+=1
                                    continue
                                elif phna_pool_name==vdlread_description:
                                    phna_read = self.pool.get('voucher.distribution.missionaries').read(cr, uid, phna_idpool[ctr],context=None)
                                    acc_read = self.pool.get('account.analytic.account').read(cr, uid, phna_read['account_id'][0],['name'])
                                    val_name = False
                                    if phna_read['national']==True:
                                        val_name = 'Philippine National'
                                    elif phna_read['national']==False:
                                        val_name = vd['name']
                                    phna_vals = {
                                            'name':val_name,
                                            'comment':vdlread['name'],
                                            'amount':vdlread['amount'],
                                            'voucher_id':vd['id'],
                                            'analytic_account_id':phna_read['account_id'][0],
                                            'account_name':acc_read['name'],
                                            }
                                    self.pool.get('voucher.distribution.voucher.transfer').create(cr, uid, phna_vals)
                        elif vdlread_description not in phna_pool:
                            val_name = 'For Account Assignment'
                            phna_vals = {
                                    'name':val_name,
                                    'comment':vdlread['name'],
                                    'amount':vdlread['amount'],
                                    'voucher_id':vd['id'],
                                    }
                            self.pool.get('voucher.distribution.voucher.transfer').create(cr, uid, phna_vals)
                        self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
        return self.check_rulings(cr, uid, ids)
    
    def check_rulings(self, cr, uid, ids, context=None):
        wildcard_pool = []
        wildcard_ids = []
        ctr=0
        wildcard_rules = self.pool.get('voucher.distribution.account.assignment').search(cr, uid, [('match_rule','=','wildcard')])
        for rule in wildcard_rules:
            ctr +=1
            wildcard_read = self.pool.get('voucher.distribution.account.assignment').read(cr, uid, rule, context=None)
            wildcard_pool.append(wildcard_read['name'])
            wildcard_ids.append(wildcard_read['id'])
        for vd in self.read(cr, uid, ids, context=None):
            for vdl in vd['voucher_lines']:
                vdlread= self.pool.get('voucher.distribution.line').read(cr, uid, vdl, context=None)
                vdlread_description = vdlread['name']
                vdlread_comments = vdlread['comments']
                lowered_description = vdlread_description.lower()
                lowered_comments = vdlread['comments'].lower()
                for rule in range(ctr):
                    wildcard_id_read = self.pool.get('voucher.distribution.account.assignment').read(cr, uid, wildcard_ids[rule],context=None)
                    if wildcard_id_read['field2match']=='description':
                        wildcard_pool_rule = wildcard_pool[rule]
                        wildcard_pool_rule = wildcard_pool_rule.lower()
                        wildcard_pool_rule=wildcard_pool_rule.replace(' ','')
                        lowered_description = lowered_description.replace(' ','')
                        if wildcard_pool_rule in lowered_description:
                            if wildcard_id_read['account_type']=='analytic':
                                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, wildcard_id_read['analytic_id'][0],context=None)
                                self.pool.get('voucher.distribution.line').write(cr, uid, vdl, {'analytic_account_id':analytic_read['id'],'account_name':analytic_read['name']})
                            elif wildcard_id_read['account_type']=='normal':
                                normal_read = self.pool.get('account.account').read(cr, uid, wildcard_id_read['account_id'][0],context=None)
                                self.pool.get('voucher.distribution.line').write(cr, uid, vdl, {'account_id':normal_read['id'],'account_name':normal_read['name']})
                        elif wildcard_pool_rule not in lowered_description:
                            continue
                    elif wildcard_id_read['field2match']=='both':
                        rule_combine = lowered_description +' '+lowered_comments
                        rule_combine = rule_combine.replace(' ','')
                        wildcard_pool_rule = wildcard_pool[rule]
                        wildcard_pool_rule = wildcard_pool_rule.lower()
                        wildcard_pool_rule=wildcard_pool_rule.replace(' ','')                       
                        if wildcard_pool_rule in rule_combine:
                            if wildcard_id_read['account_type']=='analytic':
                                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, wildcard_id_read['analytic_id'][0],context=None)
                                self.pool.get('voucher.distribution.line').write(cr, uid, vdl, {'analytic_account_id':analytic_read['id'],'account_name':analytic_read['name']})
                            elif wildcard_id_read['account_type']=='normal':
                                normal_read = self.pool.get('account.account').read(cr, uid, wildcard_id_read['account_id'][0],context=None)
                                self.pool.get('voucher.distribution.line').write(cr, uid, vdl, {'account_id':normal_read['id'],'account_name':normal_read['name']})
                        elif wildcard_pool_rule not in rule_combine:
                            continue
        return self.get_project_accounts(cr, uid, ids)
    
    def get_project_accounts(self, cr, uid, ids, context=None):
        proj_in_list = []
        for vd in self.read(cr, uid, ids, context=None):
            proj_list_check = self.pool.get('voucher.distribution.account.charging').search(cr, uid, [('voucher_id','=',vd['id'])])
            for proj_inList_item in proj_list_check:
                proj_in_list_read = self.pool.get('voucher.distribution.account.charging').read(cr, uid, proj_inList_item, ['account_id'])
                proj_in_list.append(proj_in_list_read['account_id'][0])
            proj_search = self.pool.get('account.analytic.account').search(cr, uid, [('project_account','=',True),
                                                                                     ('voucher_expense','=',False)], order='code asc')
            for proj in proj_search:
                if proj in proj_in_list:
                    continue
                elif proj not in proj_in_list:
                    projRead = self.pool.get('account.analytic.account').read(cr, uid, proj, ['name','code'])
                    vals = {
                        'name':projRead['name'],
                        'code':projRead['code'],
                        'account_id':proj,
                        'voucher_id':vd['id'],
                        }
                    self.pool.get('voucher.distribution.account.charging').create(cr, uid, vals)
            proj_search2 = self.pool.get('account.analytic.account').search(cr, uid, [('project_account','=',True),
                                                                                     ('voucher_expense','=',True)], order='code asc')
            for proj in proj_search2:
                if proj in proj_in_list:
                    continue
                elif proj not in proj_in_list:
                    projRead = self.pool.get('account.analytic.account').read(cr, uid, proj, ['name','code'])
                    vals = {
                        'name':projRead['name'],
                        'code':projRead['code'],
                        'account_id':proj,
                        'voucher_id':vd['id'],
                        'charged':True,
                        }
                    self.pool.get('voucher.distribution.account.charging').create(cr, uid, vals)
        return True
    def assignPersonalAccounts(self, cr, uid, ids, context=None):
        return True
    def count_transactions(self, cr, uid, ids, context=None):
        for vd in self.read(cr, uid, ids, context=None):
            checkLines = self.pool.get('voucher.distribution.line').search(cr, uid, [('voucher_id','=',vd['id']),
                                                                                     ('account_name','=',False)
                                                                                     ])
            if checkLines:
                raise osv.except_osv(_('Error!'), _('ERR-002: Please check all voucher lines if an account has been assigned!'))
            elif not checkLines:
                countChargedAccounts = 0
                totalGifts = 0
                chargedAccounts = self.pool.get('voucher.distribution.account.charging').search(cr, uid, [('voucher_id','=',vd['id'])])
                for charged in chargedAccounts:
                    chargedAccountsRead = self.pool.get('voucher.distribution.account.charging').read(cr, uid, charged,['account_id'])
                    lineSearch = self.pool.get('voucher.distribution.line').search(cr, uid, [('voucher_id','=',vd['id']),
                                                                                             ('amount','<','0.00'),
                                                                                             ('analytic_account_id','=',chargedAccountsRead['account_id'][0])
                                                                                             ])
                    amount = 0.00
                    for line in lineSearch:
                        self.pool.get('voucher.distribution.line').write(cr, uid, line, {'included_in_charged':True})
                        lineRead = self.pool.get('voucher.distribution.line').read(cr, uid, line, ['amount'])
                        amount+=lineRead['amount']
                    countLine = len(lineSearch)
                    totalGifts+=amount
                    countChargedAccounts+=countLine
                    self.pool.get('voucher.distribution.account.charging').write(cr, uid, charged,{'total_entries':countLine, 'entries_amount':amount})
                    
                postage_ratio = vd['recovery_charges']/countChargedAccounts
                chargedAccounts = self.pool.get('voucher.distribution.account.charging').search(cr, uid, [('voucher_id','=',vd['id']),
                                                                                                          ('charged','=',True)
                                                                                                          ])
                allChargedAmount = 0.00
                for charging in chargedAccounts:
                    charging_read = self.pool.get('voucher.distribution.account.charging').read(cr, uid, charging,['entries_amount'])
                    allChargedAmount+=charging_read['entries_amount']
                natw_ratio = vd['natw_total_charges']/allChargedAmount
                self.write(cr, uid, ids,{'postage_ratio':postage_ratio,'natw_ratio':natw_ratio,'total_gifts':totalGifts})
        return self.distribute(cr, uid, ids)
    
    def distribute(self, cr, uid, ids, context=None):
        for vd in self.read(cr, uid, ids, context=None):
            chargedAccounts = self.pool.get('voucher.distribution.account.charging').search(cr, uid, [('voucher_id','=',vd['id']),('charged','=',True)])
            for charging in chargedAccounts:
                charging_read = self.pool.get('voucher.distribution.account.charging').read(cr, uid, charging,['total_entries','entries_amount'])
                total_entry = charging_read['total_entries']
                accountAmount = charging_read['entries_amount']
                contingency = vd['contingency_ratio'] * accountAmount
                postage = vd['postage_ratio'] * total_entry
                natw=vd['natw_ratio']*accountAmount
                extra = vd['extra_ratio']*accountAmount
                total_charges = contingency + postage + natw + extra
                vals = {
                    'contingency':contingency,
                    'postage':postage,
                    'natw':natw,
                    'extra':extra,
                    'total':total_charges,
                    }
                self.pool.get('voucher.distribution.account.charging').write(cr, uid, charging, vals)
        return self.write(cr, uid, ids, {'state':'distributed'})
    
    def createMISSentry(self, cr, uid, ids, context=None):
        for vd in self.read(cr, uid, ids, context=None):
            chargedAccounts = self.pool.get('voucher.distribution.account.charging').search(cr, uid, [('voucher_id','=',vd['id'])])
            voucher_not_included = self.pool.get('voucher.distribution.line').search(cr, uid, [('voucher_id','=',vd['id']),('included_in_charged','=',False)])
            journal_id = vd['journal_id'][0]
            period_id = vd['period_id'][0]
            rate = False
            currency = False
            allDebitAmounts = False
            allCreditAmounts = False
            getCompany = self.pool.get('res.users').read(cr, uid, uid, context=None)
            getCurr = self.pool.get('res.company').read(cr, uid, getCompany['company_id'][0], ['currency_id'])
            if vd['currency_id'][0]==getCurr['currency_id'][0]:
                currency = vd['currency_id'][0]
                rate = 1.00
            elif vd['currency_id'][0]!=getCurr['currency_id'][0]:
                curr_read = self.pool.get('res.currency').read(cr, uid, vd['currency_id'][0],['rate'])
                currency = vd['currency_id'][0]
                rate = curr_read['rate']
            ffEntry = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':vd['date'],
                'ref':vd['name'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, ffEntry)
            for voucherLines in voucher_not_included:
                analytic_id = False
                account_id = False
                anaytic_name = False
                entry_amount = False
                debit = 0.00
                credit = 0.00
                lineRead = self.pool.get('voucher.distribution.line').read(cr, uid, voucherLines, context=None)
                if not lineRead['analytic_account_id']:
                    account_id = lineRead['account_id'][0]
                elif lineRead['analytic_account_id']:
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, lineRead['analytic_account_id'][0],context=None)
                    analytic_id = lineRead['analytic_account_id'][0]
                    account_id = analytic_read['normal_account'][0]
                if lineRead['amount']<0:
                    entry_amount = lineRead['amount'] * -1
                    debit = 0.00
                    credit = entry_amount / rate
                    allCreditAmounts += credit
                elif lineRead['amount']>0:
                    entry_amount = lineRead['amount']
                    debit = entry_amount / rate
                    credit = 0.00
                    allDebitAmounts +=debit
                debitEntry = debit
                creditEntry = credit
                chargedAccountEntry = {
                    'name':lineRead['name'],
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':account_id,
                    'debit':debit,
                    'credit':credit,
                    'date':vd['date'],
                    'ref':vd['name'],
                    'analytic_account_id':analytic_id, 
                    'move_id':move_id,
                    'amount_currency':lineRead['amount'],
                    'currency_id':currency,
                    }
                self.pool.get('account.move.line').create(cr, uid, chargedAccountEntry)
            for chargedAccount in chargedAccounts:
                chargedAccount_read = self.pool.get('voucher.distribution.account.charging').read(cr, uid, chargedAccount, context=None)
                if chargedAccount_read['entries_amount'] != 0.00:
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, chargedAccount_read['account_id'][0],context=None)
                    entry_amount = chargedAccount_read['entries_amount'] * -1
                    convertedAmount = entry_amount / rate
                    name = 'Fund for '+ analytic_read['name']
                    chargedAccountEntry = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':analytic_read['normal_account'][0],
                        'debit':0.00,
                        'credit':convertedAmount,
                        'date':vd['date'],
                        'ref':vd['name'],
                        'analytic_account_id':analytic_read['id'],
                        'move_id':move_id,
                        'amount_currency':entry_amount,
                        'currency_id':currency,
                        }
                    allCreditAmounts+=convertedAmount
                    self.pool.get('account.move.line').create(cr, uid, chargedAccountEntry)
                    if chargedAccount_read['contingency']!=0.00:
                        entry_amount = chargedAccount_read['contingency']
                        convertedAmount = entry_amount / rate
                        name = 'Contingency Charge for '+ analytic_read['name']
                        chargedAccountEntry = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':analytic_read['normal_account'][0],
                            'debit':convertedAmount,
                            'credit':0.00,
                            'date':vd['date'],
                            'ref':vd['name'],
                            'analytic_account_id':analytic_read['id'],
                            'move_id':move_id,
                            'amount_currency':entry_amount,
                            'currency_id':currency,
                            }
                        self.pool.get('account.move.line').create(cr, uid, chargedAccountEntry)
                        allDebitAmounts+=convertedAmount
                    if chargedAccount_read['postage']!=0.00:
                        entry_amount = chargedAccount_read['postage']
                        convertedAmount = entry_amount / rate
                        name = 'Recovery Charge for '+ analytic_read['name']
                        chargedAccountEntry = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':analytic_read['normal_account'][0],
                            'debit':convertedAmount,
                            'credit':0.00,
                            'date':vd['date'],
                            'ref':vd['name'],
                            'analytic_account_id':analytic_read['id'],
                            'move_id':move_id,
                            'amount_currency':entry_amount,
                            'currency_id':currency,
                            }
                        self.pool.get('account.move.line').create(cr, uid, chargedAccountEntry)
                        allDebitAmounts+=convertedAmount
                    if chargedAccount_read['natw']!=0.00:
                        entry_amount = chargedAccount_read['natw']
                        convertedAmount = entry_amount / rate
                        name = 'N@W Charge for '+ analytic_read['name']
                        chargedAccountEntry = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':analytic_read['normal_account'][0],
                            'debit':convertedAmount,
                            'credit':0.00,
                            'date':vd['date'],
                            'ref':vd['name'],
                            'analytic_account_id':analytic_read['id'],
                            'move_id':move_id,
                            'amount_currency':entry_amount,
                            'currency_id':currency,
                            }
                        self.pool.get('account.move.line').create(cr, uid, chargedAccountEntry)
                        allDebitAmounts+=convertedAmount
                    if chargedAccount_read['extra']!=0.00:
                        entry_amount = chargedAccount_read['extra']
                        convertedAmount = entry_amount / rate
                        name = 'Extra Charge for '+ analytic_read['name']
                        chargedAccountEntry = {
                            'name':name,
                            'journal_id':journal_id,
                            'period_id':period_id,
                            'account_id':analytic_read['normal_account'][0],
                            'debit':convertedAmount,
                            'credit':0.00,
                            'date':vd['date'],
                            'ref':vd['name'],
                            'analytic_account_id':analytic_read['id'],
                            'move_id':move_id,
                            'amount_currency':entry_amount,
                            'currency_id':currency,
                            }
                        self.pool.get('account.move.line').create(cr, uid, chargedAccountEntry)
                        allDebitAmounts+=convertedAmount
            emailCharges = self.pool.get('voucher.distribution.email.charging').search(cr, uid, [('voucher_id','=',vd['id'])])
            for email in emailCharges:
                emailChargeRead = self.pool.get('voucher.distribution.email.charging').read(cr, uid, email, context=None)
                name = emailChargeRead['name']
                if not emailChargeRead['account_id']:
                    raise osv.except_osv(_('Error!'), _('ERR-003: Please assign account to entry %s!')%(name))
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, emailChargeRead['account_id'][0],context=None)
                entry_amount = emailChargeRead['amount']
                convertedAmount = entry_amount / rate
                emailChargeEntry = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':analytic_read['normal_account'][0],
                    'debit':convertedAmount,
                    'credit':0.00,
                    'date':vd['date'],
                    'ref':vd['name'],
                    'analytic_account_id':analytic_read['id'],
                    'move_id':move_id,
                    'amount_currency':entry_amount,
                    'currency_id':currency,
                }
                self.pool.get('account.move.line').create(cr, uid, emailChargeEntry)
                allDebitAmounts+=convertedAmount
            personals= self.pool.get('voucher.distribution.personal.section').search(cr, uid, [('voucher_id','=',vd['id'])])
            for personal in personals:
                personalRead = self.pool.get('voucher.distribution.personal.section').read(cr, uid, personal, context=None)
                personal_acc_id = False
                personal_analytic_id = False
                name = personalRead['name']
                if personalRead['account_id']:
                    personal_acc_id = personalRead['account_id'][0]
                elif personalRead['analytic_id']:
                    personal_analytic_id=personalRead['analytic_id'][0]
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, personal_analytic_id,context=None)
                    personal_acc_id = analytic_read['normal_account'][0]
                elif not personalRead['account_id'] and not personalRead['analytic_id']:
                    raise osv.except_osv(_('Error!'), _('ERR-003: Please assign account to entry %s!')%(name))
                entry_amount = personalRead['amount']
                if entry_amount <0.00:
                    entry_amount = entry_amount * -1
                convertedAmount = entry_amount / rate
                if personalRead['amount'] < 0.00:
                    debit = 0.00
                    credit = convertedAmount
                    allCreditAmounts+=credit
                elif personalRead['amount']>0.00:
                    credit = 0.00
                    debit = convertedAmount
                    allDebitAmounts+=debit
                emailChargeEntry = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':personal_acc_id,
                    'debit':debit,
                    'credit':credit,
                    'date':vd['date'],
                    'ref':vd['name'],
                    'analytic_account_id':personal_analytic_id,
                    'move_id':move_id,
                    'amount_currency':entry_amount,
                    'currency_id':currency,
                }
                self.pool.get('account.move.line').create(cr, uid, emailChargeEntry)
            personals= self.pool.get('voucher.distribution.voucher.transfer').search(cr, uid, [('voucher_id','=',vd['id'])])
            for personal in personals:
                personalRead = self.pool.get('voucher.distribution.voucher.transfer').read(cr, uid, personal, context=None)
                personal_acc_id = False
                personal_analytic_id = False
                name = personalRead['comment']
                if personalRead['account_id']:
                    personal_acc_id = personalRead['account_id'][0]
                elif personalRead['analytic_account_id']:
                    personal_analytic_id=personalRead['analytic_account_id'][0]
                    analytic_read = self.pool.get('account.analytic.account').read(cr, uid, personal_analytic_id,context=None)
                    personal_acc_id = analytic_read['normal_account'][0]
                elif not personalRead['account_id'] and not personalRead['analytic_account_id']:
                    raise osv.except_osv(_('Error!'), _('ERR-003: Please assign account to entry %s!')%(name))
                entry_amount = personalRead['amount']
                if entry_amount <0.00:
                    entry_amount = entry_amount * -1
                convertedAmount = entry_amount / rate
                if personalRead['amount'] < 0.00:
                    debit = 0.00
                    credit = convertedAmount
                    allCreditAmounts+=convertedAmount
                elif personalRead['amount']>0.00:
                    credit = 0.00
                    debit = convertedAmount
                    allDebitAmounts+=convertedAmount
                emailChargeEntry = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':personal_acc_id,
                    'debit':debit,
                    'credit':credit,
                    'date':vd['date'],
                    'ref':vd['name'],
                    'analytic_account_id':personal_analytic_id,
                    'move_id':move_id,
                    'amount_currency':entry_amount,
                    'currency_id':currency,
                }
                self.pool.get('account.move.line').create(cr, uid, emailChargeEntry)
            self.write(cr, uid, ids, {'m_move_id':move_id,'state':'entry_created'})
            gainLoss = allDebitAmounts - allCreditAmounts
            entry_amount = gainLoss * rate
            uid_read = self.pool.get('res.users').read(cr, uid, uid, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, uid_read['company_id'][0],['def_gain_loss'])
            gainLossAccount = False
            if not company_read['def_gain_loss']:
                raise osv.except_osv(_('Error!'), _('Please assign exchange gain/loss account on your company!'))
            elif company_read['def_gain_loss']:
                gainLossAccount = company_read['def_gain_loss'][0]
            if allCreditAmounts>allDebitAmounts:
                debit = gainLoss * -1
                credit = 0.00
                emailChargeEntry = {
                    'name':'Exchange Gain/Loss',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':gainLossAccount,
                    'debit':debit,
                    'credit':credit,
                    'date':vd['date'],
                    'ref':vd['name'],
                    'move_id':move_id,
                    'amount_currency':entry_amount,
                    'currency_id':currency,
                }
                self.pool.get('account.move.line').create(cr, uid, emailChargeEntry)
            elif allCreditAmounts<allDebitAmounts:
                debit = 0.00
                credit = gainLoss
                emailChargeEntry = {
                    'name':'Exchange Gain/Loss',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':gainLossAccount,
                    'debit':debit,
                    'credit':credit,
                    'date':vd['date'],
                    'ref':vd['name'],
                    'move_id':move_id,
                    'amount_currency':entry_amount,
                    'currency_id':currency,
                }
                self.pool.get('account.move.line').create(cr, uid, emailChargeEntry)
        return True
    def sendEmail(self, cr, uid, ids, context=None):
        for voucher in self.read(cr, uid, ids, context=None):
            smtp_login = self.pool.get('email_template.account').search(cr, uid, [('smtpuname','ilike','openerp'),('company','=','yes')])
            use_smtp= False
            for smtp in smtp_login:
                use_smtp = smtp
            for donors in self.pool.get('voucher.distribution.natw.charge').search(cr, uid, [('voucher_id','=',voucher['id'])]):
                donorRead = self.pool.get('voucher.distribution.natw.charge').read(cr, uid, donors, context=None)
                subj = 'Thank You '+ donorRead['name']
                searchEmail = self.pool.get('res.partner.address').search(cr, uid, [('name','=',donorRead['name'])], limit=1)
                donorEmail = False
                if searchEmail:
                    emailRead = self.pool.get('res.partner.address').read(cr, uid, searchEmail[0],['email'])
                    donorEmail=emailRead['email']
                    smtp_acct = self.pool.get('email_template.account').read(cr, uid, use_smtp,['email_id'])
                    account_id = use_smtp
                    subject = 'Re:' + subj
                    email_to = donorEmail['email']
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
                    self.pool.get('email_template.mailbox').send_this_mail(cr, uid, email_lists)
        return True
                
                
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
                                    self.pool.get('email_template.mailbox').send_this_mail(cr, uid, email_lists)
        return True
    
vd()

class voucher_distribution_account_assignment(osv.osv):
    _name = 'voucher.distribution.account.assignment'
    _description = "Voucher Line Account Assignment"
    _columns = {
        'name':fields.char('Phrase',size=100),
        'field2match':fields.selection([
                                ('description','Description'),
                                ('comment','Comments'),
                                ('both','Both'),
                                ],'Fields to Match'),
        'match_rule':fields.selection([('exact','Exact Match'),('wildcard','Wildcard Match'),('prefix','Prefix Match')],'Matching Rule'),
        'account_type':fields.selection([('normal','Normal'),('analytic','Analytic')],'Account Type'),
        'account_id':fields.many2one('account.account','Normal Account'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        }
    
    _defaults = {
        'account_type':'normal',
        }
voucher_distribution_account_assignment()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,