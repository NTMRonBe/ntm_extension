
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class account_pettycash_transfer(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    _name = "account.pettycash.transfer"
    _description = "Petty Cash Fund Transfer"
    _columns = {
        'name':fields.char('Transaction No', size=64),
        'transaction_date':fields.date('Transaction Date'),
        'src_pc_id':fields.many2one('account.pettycash','Source Petty Cash'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'dest_pc_id':fields.many2one('account.pettycash','Destination Petty Cash'),
        'amount':fields.float('Amount to Transfer'),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirmed','Confirmed'),
            ('completed','Completed'),
            ('cancel','Cancelled'),
            ],'Status', select=True, readonly=True),
        }
    _defaults = {
            'name':'NEW',
            'state':'draft',
            'amount':0.00,
            'period_id':_get_period,
            }
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'account.pettycash.transfer'),
        })
        return super(account_pettycash_transfer, self).create(cr, uid, vals, context)
    
    def button_confirm(self, cr, uid, ids, context=None):
        amount = 0.00
        for pct in self.browse(cr, uid, ids, context=None):
            if pct.src_pc_id.currency_id.id!=pct.dest_pc_id.currency_id.id:
                raise osv.except_osv(_('Currency Error'),
                                            _('Currencies are not the same'))
            else:
                for pc_denom in pct.denom_breakdown:
                     quantity = pc_denom.quantity
                     multiplier = pc_denom.name.multiplier
                     amount += quantity * multiplier
                self.write(cr, uid, ids, {'state': 'confirmed','amount':amount})
        return True
    
    def button_cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancel'})    
account_pettycash_transfer()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pct_id':fields.many2one('account.pettycash.transfer','Petty Cash Transfer ID'),
        }
pettycash_denom()


class apt(osv.osv):
    _inherit = "account.pettycash.transfer"
    _columns = {
        'denom_breakdown':fields.one2many('pettycash.denom','pct_id','Denominations Breakdown',ondelete="cascade"),
        }
    def complete_transfer(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        pc_denom_pool = self.pool.get('pettycash.denom')
        pc_pool = self.pool.get('account.pettycash')
        curr_pool = self.pool.get('res.currency')
        for pct in self.read(cr, uid, ids, context=None):
            pct_id = pct['id']
            src_id = pct['src_pc_id'][0]
            dest_id = pct['dest_pc_id'][0]
            src_pca_read = pc_pool.read(cr, uid, src_id, context=None)
            dest_pca_read = pc_pool.read(cr, uid, dest_id, context=None)
            curr_id = src_pca_read['currency_id'][0]
            curr_read = curr_pool.read(cr, uid, curr_id, context=None)
            rate = curr_read = curr_read['rate']
            total_amount = pct['amount'] / rate
            pct_denom = self.pool.get('pettycash.denom').search(cr, uid, [('pct_id','=',pct_id)])
            if not pct_denom:
                raise osv.except_osv(_('Error !'), _('No denomination lines!'))
            elif pct_denom:
                for denom in pct_denom:
                    denom_read = pc_denom_pool.read(cr, uid, denom, context=None)
                    denom_id = denom_read['name'][0]
                    quantity = denom_read['quantity']
                    for src_pc in pc_denom_pool.search(cr,uid, [('pettycash_id','=',src_id),('name','=',denom_id)]):
                        src_read = pc_denom_pool.read(cr, uid, src_pc, context=None)
                        src_qty = src_read['quantity'] - quantity
                        pc_denom_pool.write(cr, uid, [src_pc],{'quantity':src_qty})
                    for dest_pc in pc_denom_pool.search(cr,uid, [('pettycash_id','=',dest_id),('name','=',denom_id)]):
                        dest_read = pc_denom_pool.read(cr, uid, dest_pc, context=None)
                        dest_qty = dest_read['quantity'] + quantity
                        pc_denom_pool.write(cr, uid, [dest_pc],{'quantity':dest_qty})
            move = {
                'name':pct['name'],
                'journal_id':pct['journal_id'][0],
                'date':pct['transaction_date'],
                'period_id':pct['period_id'][0],
                }
            move_id = move_pool.create(cr, uid, move)
            move_line = {
                'name': pct['name'],
                'credit': 0.00,
                'debit': total_amount,
                'account_id': dest_pca_read['account_code'][0],
                'move_id': move_id,
                'journal_id': pct['journal_id'][0],
                'period_id': pct['period_id'][0],
                'date': pct['transaction_date'],
                }
            move_line_pool.create(cr, uid, move_line)
            move_line = {
                'name': pct['name'],
                'debit': 0.00,
                'credit': total_amount,
                'account_id': src_pca_read['account_code'][0],
                'move_id': move_id,
                'journal_id': pct['journal_id'][0],
                'period_id': pct['period_id'][0],
                'date': pct['transaction_date'],
                }
            move_line_pool.create(cr, uid, move_line)
            move_pool.post(cr, uid, [move_id], context={})
        return self.write(cr, uid, ids, {'state':'completed'})    
apt()
