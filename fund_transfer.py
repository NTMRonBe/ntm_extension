import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class fund_transfer(osv.osv):
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    
    _name = 'fund.transfer'
    _description = "Fund Transfers"
    _columns = {
        'name':fields.related('move_id','name',type='char',size=64,store=True, string='Transfer ID',readonly=True),
        'date':fields.date('Transfer Date'),
        'type':fields.selection([
                                 ('b2b','Bank to Bank'),
                                 ('a2a','Analytic to Analytic'),
                                 ('p2b','Petty Cash to Bank')
                                 ],'Type'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal', required=True),
        'src_account':fields.many2one('account.account','Source Bank Account'),
        'pettycash_id':fields.many2one('account.pettycash','Petty Cash Account'),
        'amount':fields.float('Amount to Transfer'),
        'dest_account':fields.many2one('account.account','Destination Bank Account'),
        'src_analytic_account':fields.many2one('account.analytic.account','Source Analytic Account'),
        'dest_analytic_account':fields.many2one('account.analytic.account','Destination Analytic Account'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'state':fields.selection([
                            ('draft','Draft'),
                            ('done','Transferred'),
                            ('cancel','Cancelled'),
                            ],'State',readonly=True),
        }
    
    _defaults = {
        'period_id':_get_period,
        'state':'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        }
    
    def b2b_transfer(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        result = {}
        for b2b in self.read(cr, uid, ids, context=None):
            name = 'Fund transfer from ' + b2b['src_account'][1] + ' to ' + b2b['dest_account'][1]
            move = {
                'journal_id':b2b['journal_id'][0],
                'period_id':b2b['period_id'][0],
                'date':b2b['date'],
                'ref':name,
                }
            move_id = move_pool.create(cr, uid, move)
            credit = {
                'name':name,
                'journal_id':b2b['journal_id'][0],
                'period_id':b2b['period_id'][0],
                'date':b2b['date'],
                'account_id':b2b['src_account'][0],
                'credit':b2b['amount'],
                'move_id':move_id,
                }
            move_line_pool.create(cr, uid, credit)
            debit = {
                'name':name,
                'journal_id':b2b['journal_id'][0],
                'period_id':b2b['period_id'][0],
                'date':b2b['date'],
                'account_id':b2b['dest_account'][0],
                'debit':b2b['amount'],
                'move_id':move_id,
                }
            move_line_pool.create(cr, uid, debit)
            move_pool.post(cr, uid, [move_id],context={})
            result = {
                    'move_id':move_id,
                    'state':'done',
                    }
            self.write(cr, uid, b2b['id'],result)
        return True
    
    def a2a_transfer(self,cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        aa_pool = self.pool.get('account.analytic.account')
        for a2a in self.read(cr, uid, ids, context=None):
            src_aa_account = a2a['src_analytic_account'][0]
            dest_aa_account = a2a['dest_analytic_account'][0]
            src_read = aa_pool.read(cr, uid, src_aa_account,['normal_account'])
            src_name = src_read['normal_account'][1]
            dest_read = aa_pool.read(cr, uid, dest_aa_account,['normal_account'])
            dest_name = dest_read['normal_account'][1]
            move = {
                'journal_id':a2a['journal_id'][0],
                'period_id':a2a['period_id'][0],
                'date':a2a['date'],
                }
            move_id = move_pool.create(cr, uid, move)
            credit = {
                'name':src_name,
                'journal_id':a2a['journal_id'][0],
                'period_id':a2a['period_id'][0],
                'date':a2a['date'],
                'account_id':src_read['normal_account'][0],
                'credit':a2a['amount'],
                'analytic_account_id':src_aa_account,
                'move_id':move_id,
                }
            move_line_pool.create(cr, uid, credit)
            debit = {
                'name':dest_name,
                'journal_id':a2a['journal_id'][0],
                'period_id':a2a['period_id'][0],
                'date':a2a['date'],
                'account_id':dest_read['normal_account'][0],
                'debit':a2a['amount'],
                'analytic_account_id':dest_aa_account,
                'move_id':move_id,
                }
            move_line_pool.create(cr, uid, debit)
            #move_pool.post(cr, uid, [move_id],context={})
            result = {
                    'move_id':move_id,
                    'state':'done',
                    }
            self.write(cr, uid, a2a['id'],result)
    
    def transfer(self, cr, uid, ids, context=None):
        for transfer in self.read(cr, uid, ids, context=None):
            if transfer['type']=='b2b':
                self.b2b_transfer(cr, uid, [transfer['id']])
            elif transfer['type']=='a2a':
                self.a2a_transfer(cr, uid, [transfer['id']])
            elif transfer['type']=='p2b':
                continue
        return True
    
    def cancel(self, cr, uid, ids, context=None):
        move_pool = self.pool.get('account.move')
        for transfer in self.read(cr, uid, ids, context=None):
            if transfer['state']=='draft':
                self.write(cr, uid, transfer['id'],{'state':'cancel'})
            elif transfer['state']=='done':
                move_id = transfer['move_id'][0]
                move_pool.unlink(cr, uid, [move_id])
                self.write(cr, uid, transfer['id'],{'state':'cancel'})
        return True
    def set_to_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'draft'})
fund_transfer()

class pettycash_denom(osv.osv):
    _inherit = "pettycash.denom"
    _columns = {
        'fund_transfer_id':fields.many2one('account.pettycash',"Petty Cash ID", ondelete='cascade'),
        }
pettycash_denom()

class ft(osv.osv):
    _inherit='fund.transfer'
    _columns={
        'denom_ids':fields.one2many('pettycash.denom','fund_transfer_id','Denomination Breakdown'),
        }
ft()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,