
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
    
    def button_completed(self, cr, uid, ids, context=None):
        src_quantity = 0.00
        dest_quantity = 0.00
        denom_id = 0.00
        src_pc = self.pool.get('account.pettycash')
        dest_pc = self.pool.get('account.pettycash')
        pc_denom = self.pool.get('pettycash.denom')
        for pct in self.browse(cr, uid, ids, context=None):
            rec_id = pct.id
            src_id = pct.src_pc_id.id
            dest_id = pct.dest_pc_id.id
            for pct_denom in pct.denom_breakdown:
                denom_id = pct_denom.name.id
                quantity = pct_denom.quantity
                query=("""select * from pettycash_denom where name=%s and pettycash_id=%s""" %(denom_id, src_id))
                cr.execute(query)
                for t in cr.dictfetchall():
                    src_quantity = t['quantity']
                    id = t['id']
                    new_quantity = src_quantity - quantity
                    pc_denom.write(cr, uid, id, {'quantity':new_quantity})
                query=("""select * from pettycash_denom where name=%s and pettycash_id=%s""" %(denom_id, dest_id))
                cr.execute(query)
                for t in cr.dictfetchall():
                    src_quantity = t['quantity']
                    id = t['id']
                    new_quantity = src_quantity + quantity
                    pc_denom.write(cr, uid, id, {'quantity':new_quantity})
            amount = 0.00
            query = ("""select * from pettycash_denom where pettycash_id=%s"""%(src_id))
            cr.execute(query)
            for t in cr.dictfetchall():
                src_quantity = t['quantity']
                src_denom = t['name']
                query = ("""select * from denominations where id=%s"""%(src_denom))
                cr.execute(query)
                for t in cr.dictfetchall():
                    multiplier = t['multiplier']
                    amount+=multiplier*src_quantity
                query = ("""update account_pettycash set amount=%s where id=%s"""%(amount,src_id))
                cr.execute(query)
            query = ("""select * from pettycash_denom where pettycash_id=%s"""%(dest_id))
            cr.execute(query)
            amount = 0.00
            for t in cr.dictfetchall():
                src_quantity = t['quantity']
                src_denom = t['name']
                query = ("""select * from denominations where id=%s"""%(src_denom))
                cr.execute(query)
                for t in cr.dictfetchall():
                    multiplier = t['multiplier']
                    amount+=multiplier*src_quantity
                query = ("""update account_pettycash set amount=%s where id=%s"""%(amount,dest_id))
                cr.execute(query)   
            self.complete_pcd(cr, uid, ids)                      
        return self.write(cr, uid, ids, {'state': 'completed'})
    
    def complete_pcd(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        pc_denom = self.pool.get('pettycash.denom')
        pc_pool = self.pool.get('account.pettycash')
        rate=0.00
        for pcd in self.browse(cr, uid, ids):
            rate = pcd.src_pc_id.account_code.currency_id.rate
            total_amount = pcd.amount / rate
            move = {
                'name': pcd.name,
                'journal_id': pcd.journal_id.id,
                'date': pcd.transaction_date,
                'period_id': pcd.period_id and pcd.period_id.id or False,
                'trans_type':'pc',
            }
            move_id = move_pool.create(cr, uid, move)
            move_line = {
                'name': pcd.name or '/',
                'credit': 0.00,
                'debit': total_amount,
                'account_id': pcd.dest_pc_id.account_code.id,
                'move_id': move_id,
                'journal_id': pcd.journal_id.id,
                'period_id': pcd.period_id.id,
                'date': pcd.transaction_date,
            }
            move_line_pool.create(cr, uid, move_line)
            move_line = {
                'name': pcd.name or '/',
                'debit': 0.00,
                'credit': total_amount,
                'account_id': pcd.src_pc_id.account_code.id,
                'move_id': move_id,
                'journal_id': pcd.journal_id.id,
                'period_id': pcd.period_id.id,
                'date': pcd.transaction_date,
            }
            move_line_pool.create(cr, uid, move_line)
            move_pool.post(cr, uid, [move_id], context={})
        return True
    
apt()
