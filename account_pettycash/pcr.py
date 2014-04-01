
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
        'date':fields.date('Replenishment Date', required=True),
        'total_amount':fields.float('Total Amount'),
        'pettycash_id':fields.many2one('account.pettycash','Petty Cash Account', required=True),
        'curr_id':fields.many2one('res.currency','Currency'),
        'bank_id':fields.many2one('res.partner.bank','Bank Name', required=True),
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
            if amount == 0.00 or amount < 0.00:
                raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-022: Replenishments with no amount are not allowed!'))
            bankReader = self.pool.get('res.partner.bank').read(cr, uid, pcr.bank_id.id, ['balance'])
            if bankReader['balance']<amount:
                raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-023: Insufficient Funds! Please check your bank balance.'))
        return self.write(cr, uid, ids, {'state': 'confirmed','total_amount':amount})
    
    def button_cancel(self, cr, uid, ids, context=None):
        for pcr in self.read(cr, uid, ids, context=None):
            if pcr['state']=='confirmed':
                return self.write(cr, uid, ids, {'state': 'cancel'})
            elif pcr['state']=='completed':
                move_id = pcr['move_id'][0]
                self.pool.get('account.move').button_cancel(cr, uid, [move_id])
                self.pool.get('account.move').unlink(cr, uid, [move_id])
                for pcr_denoms in pcr['denom_breakdown']:
                    pcr_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pcr_denoms,['name','quantity'])
                    pca_denom_search = self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',pcr['pettycash_id'][0]),('name','=',pcr_denom_read['name'][0])])
                    if pca_denom_search:
                        for pca_denoms in pca_denom_search:
                            pca_denom_read = self.pool.get('pettycash.denom').read(cr, uid, pca_denoms,['quantity'])
                            pca_new_quantity = pca_denom_read['quantity'] - pcr_denom_read['quantity']
                            self.pool.get('pettycash.denom').write(cr, uid, pca_denoms,{'quantity':pca_new_quantity})
                return self.write(cr, uid, ids, {'state': 'cancel'})
        

pettycash_replenishment()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns ={
        'pcr_id':fields.many2one('pettycash.replenishment','Petty Cash ID', ondelete='cascade'),
        }    
pettycash_denom()

class pcr(osv.osv):    
    _inherit = 'pettycash.replenishment'
    _columns = {
        'denom_breakdown':fields.one2many('pettycash.denom','pcr_id','Denominations Breakdown',ondelete="cascade"),
        'filled':fields.boolean('Filled'),
        }
       
    def onchange_pettycash(self, cr, uid, ids, pettycash_id=False):
        result = {}
        if pettycash_id:
            ptc_read = self.pool.get('account.pettycash').read(cr, uid, pettycash_id,['currency_id'])
            result = {'value':{
                        'curr_id':ptc_read['currency_id'][0],
                        'bank_id':False,
                          }
                    }
        if ids:
            for p2b in self.read(cr, uid, ids, context=None):
                ftp_id = p2b['id']
                filled=False
                for p2b_denom in p2b['denom_breakdown']:
                    self.pool.get('pettycash.denom').unlink(cr, uid, p2b_denom)
                ptc_read = self.pool.get('account.pettycash').read(cr, uid, pettycash_id,['currency_id'])
                currency = ptc_read['currency_id'][1]
                denominations = self.pool.get('denominations').search(cr, uid, [('currency_id','=',ptc_read['currency_id'][0])])
                if not denominations:
                    raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-024: %s has no available denominations.Please add them!')%currency)
                new_denoms=[]
                if denominations:
                    for denom in denominations:
                        values = {
                            'name':denom,
                            'pcr_id':ftp_id,
                            }
                        denom_new= self.pool.get('pettycash.denom').create(cr, uid, values)
                        new_denoms.append(denom_new)
                result = {'value':{
                        'curr_id':ptc_read['currency_id'][0],
                        'denom_breakdown':new_denoms,
                        'bank_id':False,
                        'filled':True,
                          }
                    }
        return result
    
    def fill(self, cr, uid, ids, context=None):
        for pcr in self.read(cr, uid, ids, context=None):
            curr_id = pcr['curr_id'][0]
            currency = pcr['curr_id'][1]
            denoms = self.pool.get('denominations').search(cr, uid, [('currency_id','=',curr_id)])
            if not denoms:
                raise osv.except_osv(_('Error !'), _('ERROR CODE - ERR-024: %s has no available denominations.Please add them!')%currency)
            if denoms:
                for denom in denoms:
                    values = {
                        'name':denom,
                        'pcr_id':pcr['id'],
                    }
                    self.pool.get('pettycash.denom').create(cr, uid, values)
            self.write(cr, uid,pcr['id'],{'filled':True})
        return True
                        
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
     
    def post_pcr(self, cr, uid, ids, context=None):
        for pcr in self.read(cr, uid, ids, context=None):
            bank_read = self.pool.get('res.partner.bank').read(cr, uid, pcr['bank_id'][0],['account_id','journal_id','transit_id'])
            account_read = self.pool.get('account.account').read(cr, uid, bank_read['account_id'][0],['currency_id','company_currency_id'])
            pettycash_read = self.pool.get('account.pettycash').read(cr, uid, pcr['pettycash_id'][0],['account_code'])
            curr_rate = False
            if account_read['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, account_read['currency_id'][0],['rate'])
                curr_rate = curr_read['rate']
            if not account_read['currency_id']:
                curr_rate = 1.00
            journal_id = bank_read['journal_id'][0]
            period_id = pcr['period_id'][0]
            date=pcr['date']
            amount = pcr['total_amount'] / curr_rate
            move = {
                'journal_id':journal_id,
                'period_id':period_id,
                'date':date
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            move_line = {
                    'move_id':move_id,
                    'journal_id':journal_id,
                    'date':date,
                    'period_id':period_id,
                    'currency_id':pcr['curr_id'][0],
                }
            move_line.update({'name': 'Petty Cash Account','credit': 0.00,'debit': amount,
                              'account_id': pettycash_read['account_code'][0],'amount_currency':pcr['total_amount'],})
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line.update({'name': 'Transit to Petty Cash Account','debit': 0.00,'credit': amount,
                              'account_id': bank_read['transit_id'][0],'amount_currency':pcr['total_amount'],})
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line.update({'name': 'Transit from Bank Account','credit': 0.00,'debit': amount,
                              'account_id': bank_read['transit_id'][0],'amount_currency':pcr['total_amount'],})
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line.update({'name': 'Bank Account','debit': 0.00,'credit': amount,
                              'account_id': bank_read['account_id'][0],'amount_currency':pcr['total_amount'],})
            self.pool.get('account.move.line').create(cr, uid, move_line)
            pca_id = pcr['pettycash_id'][0]
            for denominations in pcr['denom_breakdown']:
                denom_read = self.pool.get('pettycash.denom').read(cr, uid, denominations,context=None)
                for denom_pca in self.pool.get('pettycash.denom').search(cr, uid,[('pettycash_id','=',pca_id),('name','=',denom_read['name'][0])]):
                    denom_pca_read = self.pool.get('pettycash.denom').read(cr, uid, denom_pca)
                    quantity = denom_pca_read['quantity'] + denom_read['quantity']
                    self.pool.get('pettycash.denom').write(cr, uid, denom_pca,{'quantity':quantity})
            self.pool.get('account.move').post(cr, uid, [move_id], context={})
            self.write(cr, uid, ids, {'state':'completed','move_id':move_id})
        return True

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
