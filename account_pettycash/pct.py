
import time
from osv import osv, fields, orm
import netsvc
import pooler
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
        'journal_id':fields.many2one('account.journal','Journal',domain=[('type','=','pettycash')]),
        'dest_pc_id':fields.many2one('account.pettycash','Destination Petty Cash'),
        'amount':fields.float('Amount to Transfer'),
        'move_id':fields.many2one('account.move','Move Name'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirmed','Confirmed'),
            ('completed','Completed'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        'filled':fields.boolean('Filled?'),
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
    
    def confirm(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            src_pc = pct['src_pc_id'][0]
            dest_pc = pct['dest_pc_id'][0]
            pct_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('pct_id','=',pct['id']),('quantity','>','0')])
            if not pct_denom_check:
                raise osv.except_osv(_('Error !'), _('Kindly change the quantity of the denomination to transfer!'))
            if pct_denom_check:
                amount = 0.00
                for pct_denom in pct_denom_check:
                    pct_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pct_denom,['name','quantity','amount'])
                    src_pc_denom_check= self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',src_pc),
                                                                                     ('name','=',pct_denom_read['name'][0]),
                                                                                     ])
                    for src_pc_denom in src_pc_denom_check:
                        src_pc_denom_read = self.pool.get('pettycash.denom').read(cr, uid, src_pc_denom,['name','quantity','amount'])
                        if src_pc_denom_read['quantity']<pct_denom_read['quantity']:
                            raise osv.except_osv(_('Error !'), _('Quantity of the source denomination is less than the requested quantity!'))
                        if src_pc_denom_read['quantity']>=pct_denom_read['quantity']:
                            amount +=pct_denom_read['amount']
                self.write(cr, uid, pct['id'],{'amount':amount,'state':'confirmed'})
            return True
    
    def fill(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            src_read = self.pool.get('account.pettycash').read(cr, uid, pct['src_pc_id'][0],['account_code','currency_id'])
            dest_read = self.pool.get('account.pettycash').read(cr, uid, pct['dest_pc_id'][0],['account_code','currency_id'])
            if src_read['currency_id'][0]!=dest_read['currency_id'][0]:
                raise osv.except_osv(_('Error !'), _('Source and destination pettycash accounts have different currencies!'))
            if src_read['currency_id'][0]==dest_read['currency_id'][0]: 
                currency_name = src_read['currency_id'][1]  
                check_denoms = self.pool.get('denominations').search(cr, uid, [('currency_id','=',src_read['currency_id'][0])])
                if not check_denoms:
                    raise osv.except_osv(_('Error !'), _('No available denominations for the currency!')%currency_name)
                if check_denoms:
                    for denoms in check_denoms:
                        values = {
                            'name':denoms,
                            'pct_id':pct['id'],
                            }
                        self.pool.get('pettycash.denom').create(cr, uid, values)
                        self.write(cr, uid, pct['id'],{'filled':True})
        return True
    
    def denom_change(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            src_pc = pct['src_pc_id'][0]
            dest_pc = pct['dest_pc_id'][0]
            pct_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('pct_id','=',pct['id']),('quantity','>','0')])
            for pct_denoms in  pct_denom_check:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, pct_denoms,['quantity','name'])
                src_pc_denom_check= self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',src_pc),('name','=',denom_read['name'][0])])
                netsvc.Logger().notifyChannel("src_pc_denom_check", netsvc.LOG_INFO, ' '+str(src_pc_denom_check))
                for src_pc_denom in src_pc_denom_check:
                    src_pc_denom_read = self.pool.get('pettycash.denom').read(cr, uid, src_pc_denom,['name','quantity'])
                    new_quantity = src_pc_denom_read['quantity'] - denom_read['quantity']
                    self.pool.get('pettycash.denom').write(cr, uid, src_pc_denom,{'quantity':new_quantity}) 
                    
                dest_pc_denom_check= self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',dest_pc),('name','=',denom_read['name'][0])])
                netsvc.Logger().notifyChannel("dest_pc_denom_check", netsvc.LOG_INFO, ' '+str(dest_pc_denom_check))
                for dest_pc_denom in dest_pc_denom_check:
                    dest_pc_denom_read = self.pool.get('pettycash.denom').read(cr, uid, dest_pc_denom,['name','quantity'])
                    new_quantity = dest_pc_denom_read['quantity'] + denom_read['quantity']
                    self.pool.get('pettycash.denom').write(cr, uid, dest_pc_denom,{'quantity':new_quantity})
            self.post_apt(cr, uid, ids, context)     
        return True
      
    def post_apt(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            src_read = self.pool.get('account.pettycash').read(cr, uid, pct['src_pc_id'][0],['account_code'])
            dest_read = self.pool.get('account.pettycash').read(cr, uid, pct['dest_pc_id'][0],['account_code'])
            acc_read = self.pool.get('account.account').read(cr, uid, src_read['account_code'][0],['currency_id','company_currency_id'])
            curr_rate = False
            curr_id = False
            amount = False
            if acc_read['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, acc_read['currency_id'][0],['rate'])
                curr_rate = curr_read['rate']
                amount = pct['amount'] / curr_rate
                curr_id = acc_read['currency_id'][0]
            if not acc_read['currency_id']:
                curr_rate = 1.00
                amount = pct['amount']
                curr_id = acc_read['company_currency_id'][0]
            move = {
                'journal_id':pct['journal_id'][0],
                'period_id':pct['period_id'][0],
                'date':pct['transaction_date'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            move_line = {
                'name':'Source Pettycash',
                'debit': 0.00,
                'credit': amount,
                'account_id': src_read['account_code'][0],
                'move_id': move_id,
                'journal_id':pct['journal_id'][0],
                'period_id':pct['period_id'][0],
                'date':pct['transaction_date'],
                'currency_id':curr_id,
                'amount_currency':pct['amount'],
                'post_rate':curr_rate,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line = {
                'name':'Destination Pettycash',
                'credit': 0.00,
                'debit': amount,
                'account_id': dest_read['account_code'][0],
                'move_id': move_id,
                'journal_id':pct['journal_id'][0],
                'period_id':pct['period_id'][0],
                'date':pct['transaction_date'],
                'currency_id':curr_id,
                'amount_currency':pct['amount'],
                'post_rate':curr_rate,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id], context={})
            self.write(cr, uid, ids, {'state':'completed','move_id':move_id})
        return True

apt()
