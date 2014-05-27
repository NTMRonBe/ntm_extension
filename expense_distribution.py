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
    def _compute_lines(self, cr, uid, ids, name, args, context=None):
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            src = []
            lines = []
            if invoice.move_id:
                for m in invoice.move_id.line_id:
                    temp_lines = []
                    if m.reconcile_id:
                        temp_lines = map(lambda x: x.id, m.reconcile_id.line_id)
                    elif m.reconcile_partial_id:
                        temp_lines = map(lambda x: x.id, m.reconcile_partial_id.line_partial_ids)
                    lines += [x for x in temp_lines if x not in lines]
                    src.append(m.id)

            lines = filter(lambda x: x not in src, lines)
            result[invoice.id] = lines
        return result

    _name = 'expense.distribution.generic'
    _description = "Generic Expense Distribution"
    _columns = {
        'journal_id':fields.many2one('account.journal','Expense Journal',domain=[('type','=','other_expenses')], required=True),
        'amount':fields.float('Amount to Distribute'),
        'name':fields.char('ID',size=16),
        'date':fields.date('Date'),
	'user_id':fields.many2one('res.users','Book Keeper'),
        'description':fields.text('Description'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'payment_ids': fields.function(_compute_lines, method=True, relation='account.move.line', type="many2many", string='Payments'),
        }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'name':'/',
	'user_id': lambda obj, cr, uid, context: uid,
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
        'distribution_ids':fields.one2many('expense.distribution.generic.lines','idg_id','Distribution Lines'),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('confirm','Confirmed'),
                            ('distributed','Distributed'),
                            ('paid','Paid'),
                            ('cancelled','Cancelled'),
                            ],'State')
        }
    
    def distribute(self, cr, uid, ids, context=None):
        for edg in self.read(cr, uid, ids, context=None):
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',edg['date']),('date_stop','>=',edg['date'])],limit=1)
            period_id = period_search[0]
            journal_id = edg['journal_id'][0]
            amount = edg['amount']
            date = edg['date']
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            user_id = uid
            user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['other_ap','currency_id'])
            move_line = {
                    'name':'Other Expenses',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':company_read['other_ap'][0],
                    'credit':amount,
                    'date':date,
                    'move_id':move_id,
                    'amount_currency':amount,
                    'currency_id':company_read['currency_id'][0],
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            for edgl in edg['distribution_ids']:
                edgl_read = self.pool.get('expense.distribution.generic.lines').read(cr, uid, edgl,context=None)
                analytic_read = self.pool.get('account.analytic.account').read(cr, uid, edgl_read['account_id'][0],['normal_account'])
                name = 'Expense of ' + edgl_read['account_id'][1]
                line_amount = edgl_read['amount']
                move_line = {
                    'name':name,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':analytic_read['normal_account'][0],
                    'debit':line_amount,
                    'analytic_account_id':edgl_read['account_id'][0],
                    'date':date,
                    'move_id':move_id,
                    'amount_currency':line_amount,
                    'currency_id':company_read['currency_id'][0],
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            move_read = self.pool.get('account.move').read(cr, uid, move_id,['name'])
            vals = {
                'state':'distributed',
                'move_id':move_id,
                'name':move_read['name']
                }
            self.write(cr, uid, ids, vals)
        return True
    
    def confirm(self, cr, uid, ids, context=None):
        for edg in self.read(cr, uid, ids, context=None):
            if edg['amount']==0.00:
                raise osv.except_osv(_('Error!'), _('ERROR CODE - ERR-013: Zero expense amounts are not allowed!'))
            elif edg['amount']!=0.00:
                total_amount = 0.00
                for edgl in edg['distribution_ids']:
                    edgl_read = self.pool.get('expense.distribution.generic.lines').read(cr, uid, edgl,['amount'])
                    if edgl_read['amount']==0.00:
                        raise osv.except_osv(_('Error!'), _('ERROR CODE - ERR-014: Zero charged amount is not allowed!'))
                    total_amount +=edgl_read['amount']
                if total_amount==edg['amount']:
                    self.write(cr, uid, ids, {'state':'confirm'})
                elif total_amount!=edg['amount']:
                    raise osv.except_osv(_('Error!'), _('ERROR CODE - ERR-015: Expense amount is not equal to distribution lines amount total!'))
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        for edg in self.read(cr, uid, ids, context=None):
            if edg['state']=='confirm':
                self.write(cr, uid, ids, {'state':'cancelled'})
            elif edg['state']=='distributed':
                self.pool.get('account.move').button_cancel(cr, uid, [edg['move_id'][0]])
                self.pool.get('account.move').unlink(cr, uid, [edg['move_id'][0]])
                self.write(cr, uid, ids, {'state':'cancelled'})
        return True
idg()

class expense_check_payment(osv.osv):
    _name = 'expense.check.payment'
    _description = "Expense - Check Payment"
    _columns = {
        'bank_account_id':fields.many2one('res.partner.bank','Checking Account',domain=[('ownership','=','company'),('type','=','checking')]),
        'check_number':fields.many2one('res.partner.check.numbers','Check Numbers'),
        'ref':fields.char('Reference',size=32),
        'name':fields.char('Payment Number',size=32),
        'ap_id':fields.many2one('account.account','Payables Account',domain=[('type','=','payable')]),
        'amount2pay':fields.float('Amount to Pay'),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('reserved','Reserved'),
                            ('posted','Posted'),
                            ('cancelled','Cancelled')
                            ],'State'),
        'date':fields.date('Payment Date'),
        'check_date':fields.date('Check Date'),
        }
    _defaults = {
            'state':'draft',
            'name':'/',
            'date':lambda *a: time.strftime('%Y-%m-%d'),
            }
expense_check_payment()

class res_partner_check_numbers(osv.osv):
    _inherit = 'res.partner.check.numbers'
    _columns = {
            'payment_id':fields.many2one('expense.check.payment','Payment ID', readonly=True),
            }
res_partner_check_numbers()

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
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'remarks':fields.text('Remarks'),
        }
    
    def fetch_check_num(self,cr, uid, ids, context=None):
        for ecp in self.read(cr, uid, ids, context=None):
            check_search = self.pool.get('res.partner.check.numbers').search(cr, uid, [('bank_account_id','=',ecp['bank_account_id'][0]),('state','=','available')], limit=1, order='id asc')
            if check_search:
                vals = {
                    'check_number':check_search[0]
                    }
                return self.write(cr, uid, ids, vals)
            elif not check_search:
                raise osv.except_osv(_('Error!'), _('CP-001: No check number available for the chosen checking account!'))
    
    def onchange_payables(self, cr, uid, ids, ap_id,amount2pay):
        result = {}
        payables = []
        ecp_id = False
        for ecp in self.read(cr, uid, ids, context=None):
            ecp_id = ecp['id']
        if ap_id or amount2pay:
            amount_to_pay = amount2pay
            payable_search = self.pool.get('account.move.line').search(cr, uid,[('credit','>','0.00'),('account_id','=',ap_id),('reconcile_id','=',False)])
            existing_list = self.pool.get('expense.check.payment.lines').search(cr, uid, [('payment_id','=',ecp_id)])
            self.pool.get('expense.check.payment.lines').unlink(cr, uid, existing_list)
            if amount_to_pay < 0.00:
                raise osv.except_osv(_('Error!'), _('CP-002: Negative amounts are not allowed!'))
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
                    if amount_to_pay > 0.00:
                        if amount_to_pay>=unpaid:
                            vals.update({'amount2pay':unpaid})
                        elif amount_to_pay<unpaid:
                            vals.update({'amount2pay':amount_to_pay})
                    elif amount_to_pay<0.00:
                        vals.update({'amount2pay':0.00})
                    payable_create = self.pool.get('expense.check.payment.lines').create(cr, uid, vals)
                    payables.append(payable_create)
                    amount_to_pay -=unpaid
                result = {'value':{'payment_lines':payables}}
            elif not payable_search:
                payables = []
                result = {'value':{'payment_lines':payables}}
        return result
    
    def cancel(self, cr, uid, ids, context=None):
        for ecp in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, ids, {'state':'cancelled'})
            self.pool.get('res.partner.check.numbers').write(cr, uid,ecp['check_number'][0],{'state':'cancelled'})
        return True
    
    def def_name(self, cr, uid, ids, context=None):
        for bt in self.read(cr, uid, ids, context=None):
            if bt['name']=='/':
                bank_read = self.pool.get('res.partner.bank').read(cr, uid, bt['bank_account_id'][0],['journal_id'])
                journal_read = self.pool.get('account.journal').read(cr, uid, bank_read['journal_id'][0],['sequence_id'])
                sequence_read = self.pool.get('ir.sequence').read(cr, uid, journal_read['sequence_id'][0],['code'])
                values = {
                        'name':self.pool.get('ir.sequence').get(cr, uid, sequence_read['code']),
                        }
                self.write(cr, uid, bt['id'],values)
        return True
    
    def check_lines(self, cr, uid, ids, context=None):
        for ecp in self.read(cr, uid, ids, context=None):
            amount = ecp['amount2pay']
            if amount==0.00:
                raise osv.except_osv(_('Error!'), _('Zero amounts are not allowed!'))
            line_amount = 0.00
            for lines in ecp['payment_lines']:
                ecp_read = self.pool.get('expense.check.payment.lines').read(cr, uid, lines,context=None)
                line_amount+=ecp_read['amount2pay']
            if amount>line_amount:
                raise osv.except_osv(_('Error!'), _('Amount is over the payable amount!'))
            elif amount<=line_amount:
                self.write(cr, uid, ids, {'state':'reserved'})
                self.def_name(cr, uid, ids)
                self.pool.get('res.partner.check.numbers').write(cr, uid,ecp['check_number'][0],{'state':'assigned','payment_id':ecp['id']})
        return True
    
    def post(self, cr, uid, ids, context=None):
        for check in self.read(cr, uid, ids, context=None):
            rec_list_ids = []
            bank_read = self.pool.get('res.partner.bank').read(cr, uid, check['bank_account_id'][0],context=None)
            journal_id = bank_read['journal_id'][0]
            period_search = self.pool.get('account.period').search(cr, uid, [('date_start','<=',check['date']),('date_stop','>=',check['date'])],limit=1)
            period_id = period_search[0]
            date = check['date']
            name = check['name']
            amount = check['amount2pay']
            ref = check['check_number'][1]
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date,
                'ref':ref,
                'name':name,
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            user_id = uid
            user_read = self.pool.get('res.users').read(cr, uid, user_id, ['company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, user_read['company_id'][0],['transit_php','currency_id'])
            move_line = {
                    'name':ref,
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':company_read['transit_php'][0],
                    'credit':amount,
                    'date':date,
                    'ref':name,
                    'move_id':move_id,
                    'amount_currency':amount,
                    'currency_id':company_read['currency_id'][0],
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            for ecpl in check['payment_lines']:
                ecp_read = self.pool.get('expense.check.payment.lines').read(cr, uid, ecpl,context=None)
                line_amount = ecp_read['amount2pay']
                move_line = {
                    'name':ecp_read['name'],
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':check['ap_id'][0],
                    'debit':line_amount,
                    'date':date,
                    'ref':name,
                    'move_id':move_id,
                    'amount_currency':line_amount,
                    'currency_id':company_read['currency_id'][0],
                    }
                payment = self.pool.get('account.move.line').create(cr, uid, move_line)
                rec_ids = [payment,ecp_read['move_line_id'][0]]
                rec_list_ids.append(rec_ids)
            self.pool.get('account.move').post(cr, uid, [move_id])
            read_name = self.pool.get('account.move').read(cr, uid, [move_id])
            self.write(cr, uid, ids, {
                'move_id': move_id,
                'state': 'posted',
            })
            self.pool.get('res.partner.check.numbers').write(cr, uid,check['check_number'][0],{'state':'released'})
            for rec_ids in rec_list_ids:
                if len(rec_ids) >= 2:
                    self.pool.get('account.move.line').reconcile_partial(cr, uid, rec_ids)
        return True
    
    def set2draft(self, cr, uid, ids, context=None):
        for ecp in self.read(cr, uid, ids, context=None):
            self.write(cr, uid, ids, {'state':'draft'})
        return True
ecp()


class phone_statement(osv.osv):
    def _compute_lines(self, cr, uid, ids, name, args, context=None):
        result = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            src = []
            lines = []
            if invoice.distribution_move_id:
                for m in invoice.distribution_move_id.line_id:
                    temp_lines = []
                    if m.reconcile_id:
                        temp_lines = map(lambda x: x.id, m.reconcile_id.line_id)
                    elif m.reconcile_partial_id:
                        temp_lines = map(lambda x: x.id, m.reconcile_partial_id.line_partial_ids)
                    lines += [x for x in temp_lines if x not in lines]
                    src.append(m.id)

            lines = filter(lambda x: x not in src, lines)
            result[invoice.id] = lines
        return result
    
    _inherit = 'phone.statement'
    _columns = {
        'payment_ids': fields.function(_compute_lines, method=True, relation='account.move.line', type="many2many", string='Payments'),
        }
phone_statement()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,
