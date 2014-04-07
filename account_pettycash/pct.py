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
    
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'pc_transfer')],limit=1)
        return res and res[0] or False
    
    _name = "account.pettycash.transfer"
    _description = "Petty Cash Fund Transfer"
    _columns = {
        'name':fields.char('Transaction No', size=64),
        'transaction_date':fields.date('Transaction Date'),
        'src_pc_id':fields.many2one('account.pettycash','Source Petty Cash'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal',domain=[('type','=','pc_transfer')]),
        'dest_pc_id':fields.many2one('account.pettycash','Destination Petty Cash'),
        'amount':fields.float('Amount'),
        'move_id':fields.many2one('account.move','Releasing Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'move2_id':fields.many2one('account.move','Receiving Entry'),
        'move2_ids': fields.related('move2_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'state': fields.selection([
            ('draft','Draft'),
            ('confirmed','Confirmed'),
            ('released','Released'),
            ('received','Received'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        'filled':fields.boolean('Filled?'),
        }
    _defaults = {
            'name':'NEW',
            'state':'draft',
            'journal_id':_get_journal,
            'period_id':_get_period,
            }
    def create(self, cr, uid, vals, context=None):
        vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'account.pettycash.transfer'),
        })
        return super(account_pettycash_transfer, self).create(cr, uid, vals, context)

account_pettycash_transfer()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'spct_id':fields.many2one('account.pettycash.transfer','Source Petty Cash Transfer ID', ondelete='cascade'),
        'dpct_id':fields.many2one('account.pettycash.transfer','Dest Petty Cash Transfer ID', ondelete='cascade'),
        }
pettycash_denom()


class apt(osv.osv):
    _inherit = "account.pettycash.transfer"
    _columns = {
        'sdenom_breakdown':fields.one2many('pettycash.denom','spct_id','Denominations Breakdown'),
        'ddenom_breakdown':fields.one2many('pettycash.denom','dpct_id','Denominations Breakdown'),
        }
    
    def confirm(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            src_pc = pct['src_pc_id'][0]
            dest_pc = pct['dest_pc_id'][0]
            pct_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('spct_id','=',pct['id']),('quantity','>','0')])
            if not pct_denom_check:
                raise osv.except_osv(_('Error !'), _('PCT-002: Change the quantity of the denomination to transfer!'))
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
                            raise osv.except_osv(_('Error !'), _('PCT-003: Quantity of the source denomination is less than the requested quantity!'))
                        if src_pc_denom_read['quantity']>=pct_denom_read['quantity']:
                            amount +=pct_denom_read['amount']
                self.write(cr, uid, pct['id'],{'amount':amount,'state':'confirmed'})
            return True
    
    def fill(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            src_read = self.pool.get('account.pettycash').read(cr, uid, pct['src_pc_id'][0],['account_code','currency_id'])
            dest_read = self.pool.get('account.pettycash').read(cr, uid, pct['dest_pc_id'][0],['account_code','currency_id'])
            if src_read['currency_id'][0]!=dest_read['currency_id'][0]:
                raise osv.except_osv(_('Error !'), _('PCT-001: Source and destination pettycash accounts have different currencies!'))
            if src_read['currency_id'][0]==dest_read['currency_id'][0]: 
                currency_name = src_read['currency_id'][1]  
                check_denoms = self.pool.get('denominations').search(cr, uid, [('currency_id','=',src_read['currency_id'][0])])
                if not check_denoms:
                    raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-024: No available denominations for the currency!')%currency_name)
                if check_denoms:
                    for denoms in check_denoms:
                        values = {
                            'name':denoms,
                            'spct_id':pct['id'],
                            }
                        self.pool.get('pettycash.denom').create(cr, uid, values)
                        values = {
                            'name':denoms,
                            'dpct_id':pct['id'],
                            }
                        self.pool.get('pettycash.denom').create(cr, uid, values)
                        self.write(cr, uid, pct['id'],{'filled':True})
        return True
    
    def postIT(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            if pct['state']=='confirmed':
                readSRC =self.pool.get('account.pettycash').read(cr, uid, pct['src_pc_id'][0],['manager_id'])
                if readSRC['manager_id'][0]!=uid:
                    managerName = readSRC['manager_id'][1]
                    raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-028: You are not %s! Only %s can release/receive cash for this drawer!')%(managerName,managerName))
                elif readSRC['manager_id'][0]==uid:
                    self.post_pct(cr, uid, ids, context)
            if pct['state']=='released':
                readSRC =self.pool.get('account.pettycash').read(cr, uid, pct['dest_pc_id'][0],['manager_id'])
                if readSRC['manager_id'][0]!=uid:
                    managerName = readSRC['manager_id'][1]
                    raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-028: You are not %s! Only %s can release/receive cash for this drawer!')%(managerName,managerName))
                elif readSRC['manager_id'][0]==uid:
                    self.post_pct(cr, uid, ids, context)
        return True
    
    def post_pct(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            src_pc = pct['src_pc_id'][0]
            dest_pc = pct['dest_pc_id'][0]
            pettycash_id = False
            pct_denom_check = []
            if pct['state']=='confirmed':
                pettycash_id = src_pc
                pct_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('spct_id','=',pct['id']),('quantity','>','0')])
                state='released'
            if pct['state']=='released':
                src_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('spct_id','=',pct['id']),('quantity','>','0')])
                pct_denom_check = self.pool.get('pettycash.denom').search(cr, uid, [('dpct_id','=',pct['id']),('quantity','>','0')])
                if not pct_denom_check:
                    raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-029: Kindly change the quantity of the denomination to receive!'))
                src_amount = 0
                dest_amount = 0
                for src_denoms in src_denom_check:
                    src_denoms_read = self.pool.get('pettycash.denom').read(cr, uid, src_denoms,['quantity','name'])
                    denom_multiple_read = self.pool.get('denominations').read(cr, uid, src_denoms_read['name'][0],['multiplier'])
                    src_amount += src_denoms_read['quantity'] * denom_multiple_read['multiplier']
                for dest_denoms in pct_denom_check:
                    dest_denoms_read = self.pool.get('pettycash.denom').read(cr, uid, dest_denoms,['quantity','name'])
                    denom_multiple_read = self.pool.get('denominations').read(cr, uid, dest_denoms_read['name'][0],['multiplier'])
                    dest_amount += dest_denoms_read['quantity'] * denom_multiple_read['multiplier']
                if src_amount!=dest_amount:
                    raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-030: Total amounts are not equal!'))
            for pct_denoms in pct_denom_check:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, pct_denoms,['quantity','name'])
                if pct['state']=='confirmed':
                    pc_denom_check= self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',src_pc),('name','=',denom_read['name'][0])])
                if pct['state']=='released':
                    pc_denom_check= self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',dest_pc),('name','=',denom_read['name'][0])])
                for pc_denoms in pc_denom_check:
                    pc_denoms_read = self.pool.get('pettycash.denom').read(cr, uid, pc_denoms,['name','quantity'])
                    if pct['state']=='confirmed':
                        new_quantity = pc_denoms_read['quantity']-denom_read['quantity']
                    if pct['state']=='released':
                        new_quantity = pc_denoms_read['quantity']+denom_read['quantity']
                    self.pool.get('pettycash.denom').write(cr, uid, pc_denoms,{'quantity':new_quantity})
            self.post_apt(cr, uid, ids, context)
        return True
      
    def post_apt(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            pc_id = False
            if pct['state']=='confirmed':
                pc_id = pct['src_pc_id'][0]
            if pct['state']=='released':
                pc_id = pct['dest_pc_id'][0]
            pc_read = self.pool.get('account.pettycash').read(cr, uid, pc_id,['account_code'])
            acc_read = self.pool.get('account.account').read(cr, uid, pc_read['account_code'][0],['currency_id','company_currency_id','company_id'])
            company_read = self.pool.get('res.company').read(cr, uid, acc_read['company_id'][0],['transit_php','transit_usd'])
            curr_rate = False
            curr_id = False
            transit_id=False
            amount = False
            if acc_read['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, acc_read['currency_id'][0],['rate'])
                curr_rate = curr_read['rate']
                amount = pct['amount'] / curr_rate
                curr_id = acc_read['currency_id'][0]
                transit_id = company_read['transit_usd'][0]
            if not acc_read['currency_id']:
                curr_rate = 1.00
                amount = pct['amount']
                transit_id = company_read['transit_php'][0] 
                curr_id = acc_read['company_currency_id'][0]
            if pct['state']=='confirmed':
                credit_name = 'Releasing of ' + pct['name']
                debit_name = 'Transit of ' + pct['name']
                debit_acc = transit_id
                credit_acc = pc_read['account_code'][0]
            if pct['state']=='released':
                debit_name = 'Receiving of ' + pct['name']
                credit_name = 'Transit of ' + pct['name']
                credit_acc= transit_id
                debit_acc = pc_read['account_code'][0]
            move = {
                'name':pct['name'],
                'journal_id':pct['journal_id'][0],
                'period_id':pct['period_id'][0],
                'date':pct['transaction_date'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            move_line = {
                'name':credit_name,
                'debit': 0.00,
                'credit': amount,
                'account_id': credit_acc,
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
                'name':debit_name,
                'credit': 0.00,
                'debit': amount,
                'account_id': debit_acc,
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
            if pct['state']=='confirmed':
                self.write(cr, uid, ids, {'state':'released','move_id':move_id})
            if pct['state']=='released':
                self.write(cr, uid, ids, {'state':'received','move2_id':move_id})
        return True
    
    def button_cancel(self, cr, uid, ids, context=None):
        for pct in self.read(cr, uid, ids, context=None):
            if pct['state']in ['confirmed','draft']:
                return self.write(cr,uid,ids, {'state':'cancel'})
            elif pct['state']=='released':
                self.pool.get('account.move').button_cancel(cr, uid, [pct['move_id'][0]])
                self.pool.get('account.move').unlink(cr, uid, [pct['move_id'][0]])
                for denom_line in pct['sdenom_breakdown']:
                    denom_lineReader = self.pool.get('pettycash.denom').read(cr, uid, denom_line, ['quantity','name'])
                    pc_denom_search = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_lineReader['name'][0]),
                                                                                        ('pettycash_id','=',pct['src_pc_id'][0])])
                    if pc_denom_search:
                        pc_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pc_denom_search[0],['quantity'])
                        new_qty = pc_denom_read['quantity'] + denom_lineReader['quantity']
                        self.pool.get('pettycash.denom').write(cr, uid, pc_denom_search[0], {'quantity':new_qty})
                return self.write(cr,uid,ids, {'state':'cancel'})
            elif pct['state']=='received':
                for denom_line in pct['ddenom_breakdown']:
                    denom_lineReader = self.pool.get('pettycash.denom').read(cr, uid, denom_line, ['quantity','name'])
                    pc_denom_search = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_lineReader['name'][0]),
                                                                                        ('pettycash_id','=',pct['dest_pc_id'][0])])
                    if pc_denom_search:
                        pc_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pc_denom_search[0],['quantity'])
                        if pc_denom_read['quantity'] < denom_lineReader['quantity']:
                            raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-029: Cancellation is not allowed if the destination quantity is greater than the quantity of the same denomination!'))
                        new_qty = pc_denom_read['quantity'] - denom_lineReader['quantity']
                        self.pool.get('pettycash.denom').write(cr, uid, pc_denom_search[0], {'quantity':new_qty})
                for denom_line in pct['sdenom_breakdown']:
                    denom_lineReader = self.pool.get('pettycash.denom').read(cr, uid, denom_line, ['quantity','name'])
                    pc_denom_search = self.pool.get('pettycash.denom').search(cr, uid, [('name','=',denom_lineReader['name'][0]),
                                                                                        ('pettycash_id','=',pct['src_pc_id'][0])])
                    if pc_denom_search:
                        pc_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pc_denom_search[0],['quantity'])
                        new_qty = pc_denom_read['quantity'] + denom_lineReader['quantity']
                        self.pool.get('pettycash.denom').write(cr, uid, pc_denom_search[0], {'quantity':new_qty})
                self.pool.get('account.move').button_cancel(cr, uid, [pct['move2_id'][0]])
                self.pool.get('account.move').unlink(cr, uid, [pct['move2_id'][0]])
                self.pool.get('account.move').button_cancel(cr, uid, [pct['move_id'][0]])
                self.pool.get('account.move').unlink(cr, uid, [pct['move_id'][0]])
                return self.write(cr,uid,ids, {'state':'cancel'})
            
apt()
