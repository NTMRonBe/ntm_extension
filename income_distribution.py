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
        'voucher_id':fields.many2one('voucher.distribution','Voucher ID'),
        'name':fields.char('Description',size=100),
        'comments':fields.char('Comments',size=100),
        'comments2':fields.char('Comments2',size=100),
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
voucher_distribution_line()

class vd(osv.osv):
    _inherit = 'voucher.distribution'
    _columns = {
        'missionary_lines':fields.one2many('voucher.distribution.line','voucher_id','Missionary Lines',domain=[('type','=','mission')]),
        'personal_lines':fields.one2many('voucher.distribution.line','voucher_id','Personal Lines',domain=[('type','=','personal')]),
        'voucher_lines':fields.one2many('voucher.distribution.line','voucher_id','Voucher Lines',domain=[('type','=','voucher')]),
        'other_lines':fields.one2many('voucher.distribution.line','voucher_id','Other Lines',domain=[('type','=','other')]),
        }
vd()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,