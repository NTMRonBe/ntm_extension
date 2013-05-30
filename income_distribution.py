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
        'date':fields.date('Date'),
        'move_id':fields.many2one('account.move','Move Name'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
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
        }
    
    def onchange_contribute(self, cr, uid, ids, contribute=False,amount=False):
        result = {}
        if contribute and amount:
            charge = (amount * 6.00)/100.00
            result = {'value':{'charges':charge}}
        elif amount:
            charge = (amount * 6.00)/100.00
            result = {'value':{'charges':charge}}
        elif contribute:
            charge = (amount * 6.00)/100.00
            result = {'value':{'charges':charge}}
        elif not contribute:
            result = {'value':{'charges':0.00}}
        return result
    
income_distribution_generic_lines()

class idg(osv.osv):
    _inherit = 'income.distribution.generic'
    _columns = {
        'distribution_ids':fields.one2many('income.distribution.generic.lines','idg_id','Distribution Lines')
        }
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