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

class expense_distribution_generic(osv.osv):
    _name = 'expense.distribution.generic'
    _description = "Generic Expense Distribution"
    _columns = {
        'bank_id':fields.many2one('res.partner.bank','Bank Account'),
        'amount':fields.float('Amount to Distribute'),
        'name':fields.char('ID',size=16),
        'date':fields.date('Date'),
        'description':fields.text('Description'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        }
expense_distribution_generic()

class expense_distribution_generic_lines(osv.osv):
    _name = 'expense.distribution.generic.lines'
    _description = "Distribution Lines"
    _columns = {
        'idg_id':fields.many2one('expense.distribution.generic','Distribution ID', ondelete='cascade'),
        'account_id':fields.many2one('account.analytic.account','Account'),
        'amount':fields.float('Amount'),
        }
expense_distribution_generic_lines()

class idg(osv.osv):
    _inherit = 'expense.distribution.generic'
    _columns = {
        'distribution_ids':fields.one2many('expense.distribution.generic.lines','idg_id','Distribution Lines')
        }
idg()

class expense_check_payment(osv.osv):
    _name = 'expense.check.payment'
    _description = "Expense - Check Payment"
    _columns = {
        'bank_account_id':fields.many2one('res.partner.bank','Checking Account',domain=[('ownership','=','company'),('type','=','checking')]),
        'check_number':fields.many2one('res.partner.check.numbers','Check Numbers'),
        'ref':fields.char('Reference',size=32),
        'ap_id':fields.many2one('account.account','Payables Account',domain=[('type','=','payable')]),
        'amount2pay':fields.float('Amount to Pay'),
        }
expense_check_payment()

class expense_check_payment_lines(osv.osv):
    _name = 'expense.check.payment.lines'
    _columns = {
        'move_line_id':fields.many2one('account.move.line',' Move Line'),
        'name':fields.char('Reference',size=64),
        'amount_orig':fields.float('Original Amount'),
        'amount_unpaid':fields.float('Unpaid Amount'),
        'payment_id':fields.many2one('expense.check.payment','Payment ID', ondelete='cascade'),
        'amount2pay':fields.float('Amount to Pay'),
        }
expense_check_payment_lines()

class ecp(osv.osv):
    _inherit = 'expense.check.payment'
    _columns = {
        'payment_lines':fields.one2many('expense.check.payment.lines','payment_id','Payables'),
        }
    
    def onchange_payables(self, cr, uid, ids, ap_id,amount2pay):
        result = {}
        ecp_ids = ids
        ecp_id=ecp_ids[0]
        payables = []
        if ap_id:
            amount_to_pay = amount2pay
            payable_search = self.pool.get('account.move.line').search(cr, uid,[('credit','>','0.00'),('account_id','=',ap_id),('reconcile_id','=',False)])
            existing_list = self.pool.get('expense.check.payment.lines').search(cr, uid, [('payment_id','=',ecp_id)])
            self.pool.get('expense.check.payment.lines').unlink(cr, uid, existing_list)
            if payable_search:
                for payable in payable_search:
                    check_amount = self.pool.get('account.move.line').read(cr, uid, payable,['credit','name','reconcile_partial_id'])
                    unpaid = check_amount['credit']
                    if check_amount['reconcile_partial_id']:
                        for partial_recon in self.pool.get('account.move.line').search(cr, uid,[('reconcile_partial_id','=',check_amount['reconcile_partial_id'][0])]):
                            partial_recon_read = self.pool.get('account.move.line').read(cr, uid, partial_recon,['debit'])
                            unpaid -=partial_recon_read['debit']
                    vals = {
                        'move_line_id':payable,
                        'payment_id':ecp_id,
                        'name':check_amount['name'],
                        'amount_orig':check_amount['credit'],
                        'amount_unpaid':unpaid,
                        }
                    if amount_to_pay > unpaid:
                        vals.update({'amount2pay':unpaid})
                    elif amount_to_pay<unpaid and amount_to_pay>0.00:
                        vals.update({'amount2pay':amount_to_pay})
                    elif amount_to_pay<0.00:
                        vals.update({'amount2pay':0.00})
                    payable_create = self.pool.get('expense.check.payment.lines').create(cr, uid, vals)
                    payables.append(payable_create)
                    amount_to_pay -=unpaid
                result = {'value':{'payment_lines':payables}}
            elif not payable_search:
                payables = None
                result = {'value':{'payment_lines':payables}}
        return result
ecp()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,