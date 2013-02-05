
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class cash_request_slip(osv.osv):
    _name='cash.request.slip'
    _description = "Cash Request Slip"
    _columns = {
        'name':fields.char('Cash Request Number',size=64, readonly=True),
        'requestor_id':fields.many2one('res.partner','Requestor ID'),
        'request_date':fields.date('Request Date'),
        'pc_id':fields.many2one('account.pettycash','Petty Cash Account'),
        'amount':fields.float('Amount'),
        'state': fields.selection([
            ('draft','Draft'),
            ('approval','For Approval'),
            ('approved','Approved'),
            ('cancel','Cancelled'),
            ],'Status', select=True, readonly=True),
        
        }
    _defaults={
        'request_date' : lambda *a: time.strftime('%Y-%m-%d'),
        'state':'draft',
        }
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'cash.request.slip'),
        })
        return super(cash_request_slip, self).create(cr, uid, vals, context)
    def approval(self, cr, uid, ids, context=None):
        for crs in self.browse(cr, uid, ids):
            if crs.pc_id.amount <= 0:
                self.write(cr, uid, ids, {'state':'cancel'})
            elif crs.pc_id.amount>0:
                self.write(cr, uid, ids, {'state':'approval'})
        return True
    def approved(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'approved'})
        return True
cash_request_slip()


class pettycash_disbursement(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    _name = 'pettycash.disbursement'
    _description = "Petty Cash Disbursement"
    _columns = {
        'name':fields.char('Disbursement ID',size=64),
        'journal_id':fields.many2one('account.journal','Journal'),
        'pc_id':fields.many2one('account.pettycash','Petty Cash ID'),
        'date':fields.date('Disbursement date'),
        'crs_id':fields.many2one('cash.request.slip','Cash Requests Slip'),
        'amount':fields.float('Amount', readonly=True),
        'date':fields.date('Disbursement Date'),
        'period_id':fields.many2one('account.period','Period'),
        'state': fields.selection([
            ('draft','Draft'),
            ('releasing','For Releasing'),
            ('released','Released'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        }
    _defaults = {
        'period_id':_get_period,
        'state':'draft',
        }
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'pettycash.disbursement'),
        })
        return super(pettycash_disbursement, self).create(cr, uid, vals, context)
    
pettycash_disbursement()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pd_id':fields.many2one('pettycash.disbursement','Petty Cash Disbursement ID'),
        }
pettycash_denom()

class pcd(osv.osv):
    _inherit = 'pettycash.disbursement'
    _columns = {
        'denomination_ids':fields.one2many('pettycash.denom','pd_id','Denominations Breakdown', ondelete="cascade"),
        }
    
    def compute_amount(self, cr, uid, ids, context=None):
        amount = 0.00
        for pcd in self.browse(cr, uid, ids):
            for denom in pcd.denomination_ids:
                amount += denom.quantity * denom.name.multiplier
            self.write(cr, uid, ids, {'amount':amount})
            if pcd.crs_id:
                if pcd.crs_id.amount > pcd.amount or pcd.crs_id.amount < pcd.amount:
                    raise osv.except_osv(_('Amount not equal'),
                                            _('Amounts not equal'))
                else:
                    self.write(cr, uid, ids, {'state':'releasing'})
        return True
    
    def complete_pcd(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        pc_denom = self.pool.get('pettycash.denom')
        pc_pool = self.pool.get('account.pettycash')
        analytic_pool = self.pool.get('account.analytic.line')
        rate=0.00
        for pcd in self.browse(cr, uid, ids):
            pcd_id = pcd.id
            pca_id = pcd.pc_id.id
            rate = pcd.pc_id.account_code.currency_id.rate
            for pcd_denom in pcd.denomination_ids:
                denom_id = pcd_denom.name.id
                quantity = pcd_denom.quantity
                for pcd_denom_ids in pcd.pc_id.denomination_ids:
                    pcd_denom_id = pcd_denom_ids.id
                    if pcd_denom_ids.name.id == denom_id:
                        new_quantity = pcd_denom_ids.quantity - quantity
                        pc_denom.write(cr, uid, pcd_denom_id,{'quantity':new_quantity})
            amount = 0.00
            query = ("""select * from pettycash_denom where pettycash_id=%s"""%(pca_id))
            cr.execute(query)
            for t in cr.dictfetchall():
                src_quantity = t['quantity']
                src_denom = t['name']
                query = ("""select * from denominations where id=%s"""%(src_denom))
                cr.execute(query)
                for t in cr.dictfetchall():
                    multiplier = t['multiplier']
                    amount+=multiplier*src_quantity
                query = ("""update account_pettycash set amount=%s where id=%s"""%(amount,pca_id))
                cr.execute(query)
            total_amount = pcd.amount / rate
            move = {
                'name': pcd.name,
                'journal_id': pcd.journal_id.id,
                'date': pcd.date,
                'period_id': pcd.period_id and pcd.period_id.id or False
            }
            move_id = move_pool.create(cr, uid, move)
            move_line = {
                'name': pcd.name or '/',
                'credit': 0.00,
                'debit': total_amount,
                'account_id': pcd.journal_id.default_debit_account_id.id,
                'move_id': move_id,
                'journal_id': pcd.journal_id.id,
                'period_id': pcd.period_id.id,
                'date': pcd.date,
                'trans_type':'pc',
            }
            move_line_pool.create(cr, uid, move_line)
            move_line = {
                'name': pcd.name or '/',
                'debit': 0.00,
                'credit': total_amount,
                'account_id': pcd.pc_id.account_code.id,
                'move_id': move_id,
                'journal_id': pcd.journal_id.id,
                'period_id': pcd.period_id.id,
                'date': pcd.date,
                'trans_type':'pc',
            }
            if pcd.amount > pcd.pc_id.amount:
                raise osv.except_osv(_('Insufficient funds'),
                                            _('Petty Cash has insufficient funds'))
            elif pcd.amount <= pcd.pc_id.amount:
                move_line_pool.create(cr, uid, move_line)
                move_pool.post(cr, uid, [move_id], context={})
                self.write(cr, uid, ids, {'state':'released'})
                partner_id = pcd.crs_id.requestor_id.id
                query = ("""select * from account_analytic_account where partner_id=%s"""%(partner_id))
                cr.execute(query)
                for t in cr.dictfetchall():
                    partner_id=t['id']
                analytic_line = {
                    'name':pcd.name or '/',
                    'journal_id':pcd.journal_id.analytic_journal_id.id,
                    'date':pcd.date,
                    'account_id':partner_id,
                    'amount':total_amount,
                    'general_account_id':pcd.journal_id.default_debit_account_id.id,
                }
                analytic_pool.create(cr, uid, analytic_line)
        return True
    
pcd()

class account_journal(osv.osv):
    _inherit="account.journal"
    _columns = {
        'type': fields.selection([('sale', 'Sale'),('sale_refund','Sale Refund'), 
                                ('purchase', 'Purchase'), ('purchase_refund','Purchase Refund'), 
                                ('cash', 'Cash'), ('bank', 'Bank and Cheques'), ('pettycash', 'Petty Cash'), ('disbursement', 'Petty Cash Disbursement'), 
                                ('general', 'General'), ('situation', 'Opening/Closing Situation')], 'Type', size=32, required=True,
                                 help="Select 'Sale' for Sale journal to be used at the time of making invoice."\
                                 " Select 'Purchase' for Purchase Journal to be used at the time of approving purchase order."\
                                 " Select 'Cash' to be used at the time of making payment."\
                                 " Select 'General' for miscellaneous operations."\
                                 " Select 'Petty Cash' for petty cash operations."\
                                 " Select 'Opening/Closing Situation' to be used at the time of new fiscal year creation or end of year entries generation."),
        }
account_journal()