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
                        ('received','Received'),
                        ('distributed','Distributed'),
                        ],'State')
        }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'income.distribution.generic'),
            })
        return super(income_distribution_generic, self).create(cr, uid, vals, context)
    
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
                donated_amt = idg['amount'] - idg['bank_charges']
                charge_amt = idg['bank_charges']
                amount = charge_amt / rate
                name = "Charges for donation with reference #" + idg['ref']
                move_line = {
                        'name':name,
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':company_read['bank_charge'][0],
                        'debit':amount,
                        'date':idg['rdate'],
                        'ref':idg['name'],
                        'move_id':move_id,
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
            for idgl in idg['distribution_ids']:
                idgl_read = self.pool.get('income.distribution.generic.lines').read(cr, uid, idgl, context=None)
                account_read = self.pool.get('account.analytic.account').read(cr, uid, idgl_read['account_id'][0],['normal_account'])
                distribution_amt = idgl_read['amount'] / rate
                contribution = idgl_read['charges'] / rate
                amount = "%.2f" % distribution_amt
                distribution_amt = float(amount)
                curr_distribution +=distribution_amt
                amount = "%.2f" % contribution
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
            if total_distribution != idg['amount']:
                raise osv.except_osv(_('Error !'), _('Total received amount is not equal to total distributed amount!'))
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
    _name = 'voucher.distribution'
    _description = "US and Canada Voucher Distribution"
    _columns ={
        'name':fields.char('Description',size=100),
        'date':fields.date('Date', required=True),
        'country':fields.many2one('res.country','Country',domain=[('code','in',['US','CA'])],required=True),
        'period_id':fields.many2one('account.period','Period',required=True),
        'generated':fields.boolean('Generated'),
        'missionary_subtotal':fields.float('Missionary Account Subtotal',digits_compute=dp.get_precision('Account')),
        'recovery_charges':fields.float('Recovery Charges',digits_compute=dp.get_precision('Account')),
        'natw_total_charges':fields.float('N@W Charges',digits_compute=dp.get_precision('Account')),
        'postage_recovery':fields.float('Postage Recovery Expense',digits_compute=dp.get_precision('Account')),
        'envelope_recovery':fields.float('Envelope Recovery Expense',digits_compute=dp.get_precision('Account')),
        }
    _defaults = {
            'date': lambda *a: time.strftime('%Y-%m-%d'),
            }
    
    def create(self, cr, uid, vals, context):
        period_read = self.pool.get('account.period').read(cr, uid, vals['period_id'],['name'])
        country_read = self.pool.get('res.country').read(cr, uid, vals['country'],['code'])
        name = country_read['code']+' Voucher as of '+ period_read['name']
        vals.update({
                'name': name
                })
        return super(voucher_distribution, self).create(cr, uid, vals, context)
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
        'co2':fields.char('CO2',size=10),
        'doc_num':fields.char('DOC No',size=10),
        'code':fields.char('CODE',size=10),
        'amount':fields.float('Amount'),
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
    _order = 'type asc, id asc'
    def match_account(self, cr, uid, ids, context=None):
        for vdl in self.read(cr, uid, ids, context=None):
            comment = vdl['name']
            check_exact_match = self.pool.get('voucher.distribution.rule').search(cr, uid, [('name','=',comment),('condition','=','exact')])
            if check_exact_match:
                match_read = self.pool.get('voucher.distribution.rule').read(cr, uid, check_exact_match[0], context=None)
                read_analytic = self.pool.get('account.analytic.account').read(cr, uid, match_read['account_id'][0],['name'])
                self.write(cr, uid, ids, {'analytic_account_id':match_read['account_id'][0],'account_name':read_analytic['name']})
            elif not check_exact_match:
                any= self.pool.get('voucher.distribution.rule').search(cr, uid,[('condition','=','any')])
                account_id = False
                for rule in any:
                    rule_read = self.pool.get('voucher.distribution.rule').read(cr, uid, rule, context=None)
                    read_analytic = self.pool.get('account.analytic.account').read(cr, uid, rule_read['account_id'][0],['name'])
                    if comment.find(rule_read['name'])==0:
                        self.write(cr, uid, ids, {'analytic_account_id':rule_read['account_id'][0],'account_name':read_analytic['name']})
        return True
voucher_distribution_line()

class voucher_distribution_personal_section(osv.osv):
    _name = 'voucher.distribution.personal.section'
    _description = "Personal Account Section"
    _columns = {
        'name':fields.char('Personal Account',size=64),
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
        return res
    
    def onchange_analyticid(self, cr, uid, ids, analytic_id):
        res = {}
        if analytic_id:
            accountRead = self.pool.get('account.analytic.account').read(cr, uid, analytic_id, ['name'])
            res = {'value':{'account_id':analytic_id,'account_name':accountRead['name'], 'account_id':False}}
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
        'name':fields.char('Email Account (Voucher)',size=64),
        'description':fields.char('Description',size=64),
        'account_id':fields.many2one('account.analytic.account','Analytic Account')
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
        'name':fields.many2one('account.analytic.account','Account Charged'),
        'contingency':fields.float('Contingency Charges'),
        'postage':fields.float('Postage/Env Recovery'),
        'natw':fields.float('N@W Charges'),
        'extra':fields.float('Extra Charges'),
        'total':fields.float('Total'),
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade'),
        }
voucher_distribution_account_charging()

class voucher_distribution_9phna(osv.osv):
    _name = 'voucher.distribution.missionaries'
    _description = "Missionary Charging"
    _columns = {
        'name':fields.char('Name',size=64),
        'account_id':fields.many2one('account.analytic.account','Account Name'),
        'national':fields.boolean('Philippine National'),
        }
voucher_distribution_9phna()

class voucher_distribution_uncharged(osv.osv):
    _name = 'voucher.distribution.uncharged'
    _description = "Uncharged Amounts"
    _columns = {
        'name':fields.char('Description',size=64),
        'amount':fields.float('Amount',size=64),
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID',ondelete='cascade')
        }
voucher_distribution_uncharged()

class voucher_distribution_voucher_transfer(osv.osv):
    _name = 'voucher.distribution.voucher.transfer'
    _description = "Voucher Transfer"
    _columns = {
        'name':fields.char('Description',size=64),
        'comment':fields.char('Comments',size=64),
        'amount':fields.float('Amount',digits_compute=dp.get_precision('Account')),
        'account_name':fields.char('Account Name',size=100),
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
        return res
    
    def onchange_analytic(self, cr, uid, ids,analytic_account_id):
        res = {}
        if analytic_account_id:
            acc_read = self.pool.get('account.analytic.account').read(cr, uid, analytic_account_id, ['name'])
            res = {'value':{'account_name':acc_read['name']}}
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
        'uncharged_ids':fields.one2many('voucher.distribution.uncharged','voucher_id','Uncharged Amounts'),
        }
    def match_accounts(self, cr, uid, ids, context=None):
        for vd in self.read(cr, uid, ids, context=None):
            for vdl in vd['voucher_lines']:
                self.pool.get('voucher.distribution.line').match_account(cr, uid, [vdl])
        return True
    
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
                    print vdlread_comments
                    email_search = self.pool.get('email.charging.account').search(cr, uid, [('name','=',vdlread_comments)], limit=1)
                    if email_search:
                        email_read = self.pool.get('email.charging.account').read(cr, uid, email_search[0], context=None)
                        print email_read
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
                    if vdlread_code=='md':
                        uncharged_vals = {
                                'name':vdlread['name'],
                                'amount':vdlread['amount'],
                                'voucher_id':vd['id'],
                                }
                        self.pool.get('voucher.distribution.uncharged').create(cr, uid, uncharged_vals)
                        self.pool.get('voucher.distribution.line').unlink(cr, uid, vdl)
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
        return True
                    
            
                
vd()
class voucher_distribution_rule(osv.osv):
    _name = 'voucher.distribution.rule'
    _description = "Distribution Rules"
    _columns = {
        'name':fields.char('Phrase 1',size=100),
        'name2':fields.char('Phrase 2',size=100),
        'account_id':fields.many2one('account.analytic.account','Account Name'),
        'condition':fields.selection([
                            ('exact','Exact Match'),
                            ('both','Both words in phrase'),
                            ('any','Any word in phrase')
                            ],'Condition'),
        } 
voucher_distribution_rule()


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