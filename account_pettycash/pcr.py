
import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class pettycash_replenishment(osv.osv):    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
            
    _name = 'pettycash.replenishment'
    _description = "PettyCash Replenishment"
    _columns = {
        'name':fields.char('Replenishment ID',size=64, readonly=True),
        'date':fields.date('Replenishment Date'),
        'total_amount':fields.float('Total Amount'),
        'pettycash_id':fields.many2one('account.pettycash','Petty Cash Account'),
        'journal_id':fields.many2one('account.journal', 'Journal', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'period_id':fields.many2one('account.period','Period'),
        'move_id':fields.many2one('account.move','Move Name'),
        'move_ids':fields.one2many('account.move.line','move_id','Journal Items',ondelete="cascade"),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirmed','Confirmed'),
            ('completed','Completed'),
            ('cancel','Cancelled'),
            ],'Status', select=True, readonly=True),
        }
    _defaults={
        'name':'NEW',
        'state':'draft',
        'period_id':_get_period,
        }
    
    def _get_special_deduction_ids(self, cr, uid, context=None):
        mids = self.search(cr, uid, [('move_id', '=', uid)], context=context)
        result = {uid: 1}
        for m in self.browse(cr, uid, mids, context=context):
            for user in m.move_ids:
                result[user.id] = 1
        return result.keys()
    
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'pettycash.replenishment'),
        })
        return super(pettycash_replenishment, self).create(cr, uid, vals, context)
    
    def confirm_pcr(self, cr, uid, ids, context=None):
        amount = 0.00
        for pcr in self.browse(cr, uid, ids, context=None):
            for pc_denom in pcr.denom_breakdown:
                 quantity = pc_denom.quantity
                 multiplier = pc_denom.name.multiplier
                 amount += quantity * multiplier
                 netsvc.Logger().notifyChannel("Denominations", netsvc.LOG_INFO, ' '+str(quantity))
                 netsvc.Logger().notifyChannel("Denominations", netsvc.LOG_INFO, ' '+str(multiplier))
                 netsvc.Logger().notifyChannel("Denominations", netsvc.LOG_INFO, ' '+str(amount))
        return self.write(cr, uid, ids, {'state': 'confirmed','total_amount':amount})
    
    def button_cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancel'})

pettycash_replenishment()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pcr_id':fields.many2one('pettycash.replenishment','Petty Cash ID'),
        }    
pettycash_denom()

class pcr(osv.osv):    
    _inherit = 'pettycash.replenishment'
    _columns = {
        'denom_breakdown':fields.one2many('pettycash.denom','pcr_id','Denominations Breakdown',ondelete="cascade"),
        }
        
    def complete_pcr(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        pc_denom = self.pool.get('pettycash.denom')
        pc_pool = self.pool.get('account.pettycash')
        rate=0.00
        for pcr in self.browse(cr, uid, ids):
            pcr_id = pcr.id
            pca_id = pcr.pettycash_id.id
            rate = pcr.pettycash_id.account_code.currency_id.rate
            for pcr_denom in pcr.denom_breakdown:
                denom_id = pcr_denom.name.id
                quantity = pcr_denom.quantity
                for pcr_denom_ids in pcr.pettycash_id.denomination_ids:
                    pcr_denom_id = pcr_denom_ids.id
                    if pcr_denom_ids.name.id == denom_id:
                        new_quantity = pcr_denom_ids.quantity + quantity
                        pc_denom.write(cr, uid, pcr_denom_id,{'quantity':new_quantity})
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
            total_amount = pcr.total_amount / rate
            move = {
                'name': pcr.name,
                'journal_id': pcr.journal_id.id,
                'date': pcr.date,
                'period_id': pcr.period_id and pcr.period_id.id or False
            }
            move_id = move_pool.create(cr, uid, move)
            move_line = {
                'name': pcr.name or '/',
                'debit': 0.00,
                'credit': total_amount,
                'account_id': pcr.journal_id.default_debit_account_id.id,
                'move_id': move_id,
                'journal_id': pcr.journal_id.id,
                'period_id': pcr.period_id.id,
                'date': pcr.date,
                'trans_type':'pc',
            }
            move_line_pool.create(cr, uid, move_line)
            move_line = {
                'name': pcr.name or '/',
                'credit': 0.00,
                'debit': total_amount,
                'account_id': pcr.pettycash_id.account_code.id,
                'move_id': move_id,
                'journal_id': pcr.journal_id.id,
                'period_id': pcr.period_id.id,
                'date': pcr.date,
                'trans_type':'pc',
            }
            move_line_pool.create(cr, uid, move_line)
            move_pool.post(cr, uid, [move_id], context={})
        return self.write(cr, uid, ids, {'move_id':move_id,'state':'completed'})
pcr()