import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from stringprep import b1_set

class iat(osv.osv):
    _inherit = 'internal.account.transfer'
    
    def transfer(self, cr, uid, ids, context=None):
        if 'transfer_type' in context:
            if context['transfer_type']=='people2proj':
                for iat in self.read(cr, uid, ids, context=None):
                    if not iat['multiple']:
                        self.notmultiple(cr, uid, ids)
                    if iat['multiple']:
                        self.ifmultiple(cr, uid, ids)
            if context['transfer_type']=='proj2people':
                for iat in self.read(cr, uid, ids, context=None):
                    if not iat['multiple']:
                        self.notmultiple(cr, uid, ids)
                    if iat['multiple']:
                        self.ifmultiple(cr, uid, ids)
            if context['transfer_type']=='people2pc':
                self.check_denoms(cr, uid, ids)
            if context['transfer_type']=='proj2pc':
                self.check_denoms(cr, uid, ids)
            if context['transfer_type']=='income2pc':
                self.check_denoms(cr, uid, ids)
            if context['transfer_type']=='people2people':
                for iat in self.read(cr, uid, ids, context=None):
                    if not iat['multiple']:
                        self.notmultiple(cr, uid, ids)
                    if iat['multiple']:
                        self.ifmultiple(cr, uid, ids)
            if context['transfer_type']=='proj2proj':
                for iat in self.read(cr, uid, ids, context=None):
                    if not iat['multiple']:
                        self.notmultiple(cr, uid, ids)
                    if iat['multiple']:
                        self.ifmultiple(cr, uid, ids)
    
    def people2pc(self, cr, uid, ids, context=None):
        for iat in self.read(cr, uid, ids, context=None):
            journal_id = iat['journal_id'][0]
            period_id = iat['period_id'][0]
            move = {
                'ref':iat['name'],
                'journal_id':iat['journal_id'][0],
                'period_id':iat['period_id'][0],
                'date':iat['date'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, iat['src_pat_analytic_id'][0],context=None)
            analytic_name = analytic_read['name']
            pc_read = self.pool.get('account.pettycash').read(cr, uid, iat['pettycash_id'][0],context=None)
            check_currency = self.pool.get('account.account').read(cr, uid, pc_read['account_code'][0],['currency_id','company_currency_id'])
            currency = False
            rate = False
            if not check_currency['currency_id']:
                currency = check_currency['company_currency_id'][0]
                rate = 1.00
            if check_currency['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, check_currency['currency_id'][0],['rate'])
                currency = check_currency['currency_id'][0]
                rate = curr_read['rate']
            amount = iat['amount'] / rate
            if not analytic_read['normal_account']:
                raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
            move_line = {
                    'name':'Source Account',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':analytic_read['normal_account'][0],
                    'credit':amount,
                    'analytic_account_id':analytic_read['id'],
                    'date':iat['date'],
                    'ref':iat['name'],
                    'move_id':move_id,
                    'amount_currency':iat['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line = {
                    'name':'Destination Petty Cash',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':pc_read['account_code'][0],
                    'debit':amount,
                    'date':iat['date'],
                    'ref':iat['name'],
                    'move_id':move_id,
                    'amount_currency':iat['amount'],
                    'currency_id':currency,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'move_id':move_id,'state':'transfer'})
        return True
    def proj2pc(self, cr, uid, ids, context=None):
        for iat in self.read(cr, uid, ids, context=None):
            journal_id = iat['journal_id'][0]
            period_id = iat['period_id'][0]
            move = {
                'ref':iat['name'],
                'journal_id':iat['journal_id'][0],
                'period_id':iat['period_id'][0],
                'date':iat['date'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, iat['src_proj_analytic_id'][0],context=None)
            analytic_name = analytic_read['name']
            pc_read = self.pool.get('account.pettycash').read(cr, uid, iat['pettycash_id'][0],context=None)
            check_currency = self.pool.get('account.account').read(cr, uid, pc_read['account_code'][0],['currency_id','company_currency_id'])
            currency = False
            rate = False
            if not check_currency['currency_id']:
                currency = check_currency['company_currency_id'][0]
                rate = 1.00
            if check_currency['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, check_currency['currency_id'][0],['rate'])
                currency = check_currency['currency_id'][0]
                rate = curr_read['rate']
            amount = iat['amount'] / rate
            if not analytic_read['normal_account']:
                raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
            move_line = {
                    'name':'Source Account',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':analytic_read['normal_account'][0],
                    'credit':amount,
                    'analytic_account_id':analytic_read['id'],
                    'date':iat['date'],
                    'ref':iat['name'],
                    'move_id':move_id,
                    'amount_currency':iat['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line = {
                    'name':'Destination Petty Cash',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':pc_read['account_code'][0],
                    'debit':amount,
                    'date':iat['date'],
                    'ref':iat['name'],
                    'move_id':move_id,
                    'amount_currency':iat['amount'],
                    'currency_id':currency,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'move_id':move_id,'state':'transfer'})
        return True
    
    def income2pc(self, cr, uid, ids, context=None):
        for iat in self.read(cr, uid, ids, context=None):
            journal_id = iat['journal_id'][0]
            period_id = iat['period_id'][0]
            move = {
                'ref':iat['name'],
                'journal_id':iat['journal_id'][0],
                'period_id':iat['period_id'][0],
                'date':iat['date'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            analytic_read = self.pool.get('account.analytic.account').read(cr, uid, iat['src_income_analytic_id'][0],context=None)
            analytic_name = analytic_read['name']
            pc_read = self.pool.get('account.pettycash').read(cr, uid, iat['pettycash_id'][0],context=None)
            check_currency = self.pool.get('account.account').read(cr, uid, pc_read['account_code'][0],['currency_id','company_currency_id'])
            currency = False
            rate = False
            if not check_currency['currency_id']:
                currency = check_currency['company_currency_id'][0]
                rate = 1.00
            if check_currency['currency_id']:
                curr_read = self.pool.get('res.currency').read(cr, uid, check_currency['currency_id'][0],['rate'])
                currency = check_currency['currency_id'][0]
                rate = curr_read['rate']
            amount = iat['amount'] / rate
            if not analytic_read['normal_account']:
                raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
            move_line = {
                    'name':'Source Account',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':analytic_read['normal_account'][0],
                    'credit':amount,
                    'analytic_account_id':analytic_read['id'],
                    'date':iat['date'],
                    'ref':iat['name'],
                    'move_id':move_id,
                    'amount_currency':iat['amount'],
                    'currency_id':currency,
                    }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            move_line = {
                    'name':'Destination Petty Cash',
                    'journal_id':journal_id,
                    'period_id':period_id,
                    'account_id':pc_read['account_code'][0],
                    'debit':amount,
                    'date':iat['date'],
                    'ref':iat['name'],
                    'move_id':move_id,
                    'amount_currency':iat['amount'],
                    'currency_id':currency,
                }
            self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'move_id':move_id,'state':'transfer'})
        return True
    
    def check_denoms(self, cr, uid, ids, context=None):
        for iat in self.read(cr, uid, ids, context=None):
            total_denom_amount=0.00
            for iatd in iat['denom_ids']:
                iatd_read = self.pool.get('pettycash.denom').read(cr, uid, iatd, ['quantity','name'])
                denom_check = self.pool.get('denominations').read(cr, uid, iatd_read['name'][0],['multiplier'])
                total_denom_amount +=iatd_read['quantity']*denom_check['multiplier']
            if total_denom_amount!=iat['amount']:
                raise osv.except_osv(_('Error!'), _('Sum of all denominations is not equal to the amount to be transferred!'))
            elif total_denom_amount==iat['amount']:
                for iatd in iat['denom_ids']:
                    iatd_read = self.pool.get('pettycash.denom').read(cr, uid, iatd, ['quantity','name'])
                    pc_check = self.pool.get('pettycash.denom').search(cr, uid, [('pettycash_id','=',iat['pettycash_id'][0]),
                                                                                ('name','=',iatd_read['name'][0])])
                    pc_read = self.pool.get('pettycash.denom').read(cr, uid, pc_check[0],['quantity'])
                    newdenom = iatd_read['quantity'] + pc_read['quantity']
                    self.pool.get('pettycash.denom').write(cr, uid, pc_check[0],{'quantity':newdenom})
            if iat['transfer_type']=='people2pc':
                self.people2pc(cr, uid, ids)
            elif iat['transfer_type']=='proj2pc':
                self.proj2pc(cr, uid, ids)
            elif iat['transfer_type']=='income2pc':
                self.income2pc(cr, uid, ids)
        return True
                    
                    
                    
        
    def notmultiple(self, cr, uid, ids, context=None):
        for iat in self.read(cr, uid, ids, context=None):
            journal_id = iat['journal_id'][0]
            period_id = iat['period_id'][0]
            move = {
                'ref':iat['name'],
                'journal_id':iat['journal_id'][0],
                'period_id':iat['period_id'][0],
                'date':iat['date'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            src_account = 0
            dest_account = 0
            currency = False
            rate = False
            analytic_name = False
            if iat['transfer_type']=='people2people':
                src_account = iat['src_pat_analytic_id'][0]
                dest_account = iat['dest_pat_analytic_id'][0]
            if iat['transfer_type']=='people2proj':
                src_account = iat['src_pat_analytic_id'][0]
                dest_account = iat['dest_proj_analytic_id'][0]
            if iat['transfer_type']=='proj2people':
                src_account = iat['src_proj_analytic_id'][0]
                dest_account = iat['dest_pat_analytic_id'][0]
            if iat['transfer_type']=='proj2proj':
                src_account = iat['src_proj_analytic_id'][0]
                dest_account = iat['dest_proj_analytic_id'][0]
            if src_account==dest_account:
                raise osv.except_osv(_('Error !'), _('Source and destination PAT accounts must not be the same!'))
            if src_account!=dest_account:
                src_analytic_read = self.pool.get('account.analytic.account').read(cr, uid,src_account,context=None)
                dest_analytic_read = self.pool.get('account.analytic.account').read(cr, uid, dest_account,context=None)
                check_currency = self.pool.get('account.account').read(cr, uid, src_analytic_read['normal_account'][0],['currency_id','company_currency_id'])
                curr_read = self.pool.get('res.currency').read(cr, uid, iat['currency_id'][0],['rate'])
                currency = curr_read['id']
                rate = curr_read['rate']
                amount = iat['amount'] / rate
                if not src_analytic_read['normal_account']:
                    analytic_name = src_analytic_read['name']
                    raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
                if not dest_analytic_read['normal_account']:
                    analytic_name = src_analytic_read['name']
                    raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
                move_line = {
                        'name':'Source Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':src_analytic_read['normal_account'][0],
                        'credit':amount,
                        'analytic_account_id':dest_analytic_read['id'],
                        'date':iat['date'],
                        'ref':iat['name'],
                        'move_id':move_id,
                        'amount_currency':iat['amount'],
                        'currency_id':currency,
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                move_line = {
                        'name':'Destination Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':dest_analytic_read['normal_account'][0],
                        'debit':amount,
                        'analytic_account_id':src_analytic_read['id'],
                        'date':iat['date'],
                        'ref':iat['name'],
                        'move_id':move_id,
                        'amount_currency':iat['amount'],
                        'currency_id':currency,
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                self.pool.get('account.move').post(cr, uid, [move_id])
                self.write(cr, uid, ids, {'move_id':move_id,'state':'transfer'})
        return True
    
    def ifmultiple(self, cr, uid, ids, context=None):
        for iat in self.read(cr, uid, ids, context=None):
            journal_id = iat['journal_id'][0]
            period_id = iat['period_id'][0]
            move = {
                'ref':iat['name'],
                'journal_id':iat['journal_id'][0],
                'period_id':iat['period_id'][0],
                'date':iat['date'],
                }
            move_id = self.pool.get('account.move').create(cr, uid, move)
            src_account = 0
            dest_account = []
            currency = False
            rate = False
            analytic_name = False
            if iat['transfer_type']=='people2people':
                src_account = iat['src_pat_analytic_id'][0]
                dest_account = iat['pat_iatd_ids']
            if iat['transfer_type']=='people2proj':
                src_account = iat['src_pat_analytic_id'][0]
                dest_account = iat['proj_iatd_ids']
            if iat['transfer_type']=='proj2people':
                src_account = iat['src_proj_analytic_id'][0]
                dest_account = iat['pat_iatd_ids']
            if iat['transfer_type']=='proj2proj':
                src_account = iat['src_proj_analytic_id'][0]
                dest_account = iat['proj_iatd_ids']
            if not dest_account:
                raise osv.except_osv(_('Error !'), _('Please add destination accounts!'))
            src_analytic_read = self.pool.get('account.analytic.account').read(cr, uid,src_account,context=None)
            curr_read = self.pool.get('res.currency').read(cr, uid, iat['currency_id'][0],['rate'])
            currency = curr_read['id']
            rate = curr_read['rate']
            if not src_analytic_read['normal_account']:
                analytic_name = src_analytic_read['name']
                raise osv.except_osv(_('Error !'), _('Please add a related account to %s')%analytic_name)
            for dest_account_ids in dest_account:
                dest_acc = False
                iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid,dest_account_ids,context=None)
                if iat['transfer_type'] in ['people2people','proj2people']:
                    dest_acc = iatd_read['pat_analytic_id'][0]
                if iat['transfer_type'] in ['people2proj','proj2proj']:
                    dest_acc = iatd_read['proj_analytic_id'][0]
                dest_analytic_read = self.pool.get('account.analytic.account').read(cr, uid, dest_acc,context=None)
                amount = iatd_read['amount'] / rate
                move_line = {
                        'name':'Source Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':src_analytic_read['normal_account'][0],
                        'credit':amount,
                        'analytic_account_id':dest_analytic_read['id'],
                        'date':iat['date'],
                        'ref':iat['name'],
                        'move_id':move_id,
                        'amount_currency':iatd_read['amount'],
                        'currency_id':currency,
                        }
                self.pool.get('account.move.line').create(cr, uid, move_line)
                move_line = {
                        'name':'Destination Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':dest_analytic_read['normal_account'][0],
                        'debit':amount,
                        'analytic_account_id':src_analytic_read['id'],
                        'date':iat['date'],
                        'ref':iat['name'],
                        'move_id':move_id,
                        'amount_currency':iatd_read['amount'],
                        'currency_id':currency,
                    }
                self.pool.get('account.move.line').create(cr, uid, move_line)
            self.pool.get('account.move').post(cr, uid, [move_id])
            self.write(cr, uid, ids, {'move_id':move_id,'state':'transfer'})
        return True
            
iat()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,