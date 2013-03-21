
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
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirmed','Confirmed'),
            ('completed','Completed'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        }
    _defaults={
        'name':'NEW',
        'state':'draft',
        'period_id':_get_period,
        }
    
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
    
    def compute_pc(self, cr, uid, ids, context=None):
        for pcr in self.read(cr, uid, ids, context=None):
            amount=0.00
            amount_pca = 0.00
            for denominations in self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',pcr['pettycash_id'][0])]):
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, denominations,context=None)
                denom_reader = self.pool.get('denominations').read(cr, uid, denom_read['name'][0],['multiplier'])
                amount = denom_read['quantity'] * denom_reader['multiplier']
                amount_pca += amount
                self.pool.get('pettycash.denom').write(cr, uid, denominations,{'amount_total':amount})
            self.pool.get('account.pettycash').write(cr, uid, pcr['pettycash_id'][0],{'amount':amount_pca})
        return self.write(cr, uid, ids,{'state':'completed'})
    
    def complete(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        pc_denom = self.pool.get('pettycash.denom')
        pc_pool = self.pool.get('account.pettycash')
        for pcr in self.read(cr, uid, ids,context=None):
            journal_read = self.pool.get('account.journal').read(cr, uid, pcr['journal_id'][0],['default_debit_account_id'])
            account_read = pc_pool.read(cr, uid, pcr['pettycash_id'][0],['account_code'])
            move = {
                'name': pcr['name'],
                'journal_id': pcr['journal_id'][0],
                'date': pcr['date'],
                'period_id': pcr['period_id'][0],
                }
            pcr_id = pcr['id']
            move_id = move_pool.create(cr, uid, move)
            self.write(cr, uid, ids, {'move_id':move_id})
            move_line = {
                'name': pcr['name'] or '/',
                'debit': 0.00,
                'credit': pcr['total_amount'],
                'account_id': journal_read['default_debit_account_id'][0],
                'move_id': move_id,
                'journal_id': pcr['journal_id'][0],
                'period_id': pcr['period_id'][0],
                'date': pcr['date'],
            }
            move_line_pool.create(cr, uid, move_line)
            move_line = {
                'name': pcr['name'] or '/',
                'credit': 0.00,
                'debit': pcr['total_amount'],
                'account_id': account_read['account_code'][0],
                'move_id': move_id,
                'journal_id': pcr['journal_id'][0],
                'period_id': pcr['period_id'][0],
                'date': pcr['date'],
            }
            pca_id = pcr['pettycash_id'][0]
            move_line_pool.create(cr, uid, move_line)
            for denominations in pc_denom.search(cr, uid, [('pcr_id','=',pcr_id)]):
                denom_read = pc_denom.read(cr, uid, denominations,context=None)
                netsvc.Logger().notifyChannel("denom_read", netsvc.LOG_INFO, ' '+str(denom_read))
                for denom_pca in pc_denom.search(cr, uid,[('pettycash_id','=',pca_id),('name','=',denom_read['name'][0])]):
                    denom_pca_read = pc_denom.read(cr, uid, denom_pca)
                    netsvc.Logger().notifyChannel("denom_pca_read", netsvc.LOG_INFO, ' '+str(denom_pca_read))
                    quantity = denom_pca_read['quantity'] + denom_read['quantity']
                    pc_denom.write(cr, uid, denom_pca,{'quantity':quantity})
            move_pool.post(cr, uid, [move_id], context={})
        return self.compute_pc(cr, uid,ids)
pcr()
