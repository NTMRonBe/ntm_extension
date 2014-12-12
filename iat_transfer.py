import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class internal_account_transfer(osv.osv):
    def _get_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'iat')],limit=1)
        return res and res[0] or False
    
    def _get_period(self, cr, uid, context=None):
        if context is None: context = {}
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        return periods and periods[0] or False
    
    _name = 'internal.account.transfer'
    _description = 'Internal Account Transfers'
    _columns = {
        'name':fields.char('Transfer ID',size=32),
        'remarks':fields.text('Remarks'),
        'date':fields.date('Date'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal',domain=[('type','=','iat')]),
        'src_pat_analytic_id':fields.many2one('account.analytic.account','PAT Account',domain=[('supplier','=',True)]),
        'src_income_analytic_id':fields.many2one('account.analytic.account','Income Account',domain=[('ntm_type','=','income')]),
        'src_expense_analytic_id':fields.many2one('account.analytic.account','Expense Account',domain=[('ntm_type','=','expense')]),
        'src_proj_analytic_id':fields.many2one('account.analytic.account','Project Account', domain=[('project','=',True)]),
        'dest_pat_analytic_id':fields.many2one('account.analytic.account','PAT Account', domain=[('supplier','=',True)]),
        'dest_proj_analytic_id':fields.many2one('account.analytic.account','Project Account', domain=[('project','=',True)]),
        'dest_income_analytic_id':fields.many2one('account.analytic.account','Income Account', domain=[('ntm_type','=','income')]),
        'transfer_type':fields.selection([
                                ('people2proj','PAT to Project Account'),
                                ('proj2proj','Project to Project Account'),
                                ('people2people','PAT to PAT Account'),
                                ('proj2people','Project to PAT Account'),
                                ('people2pc','PAT to Petty Cash Account'),
                                ('people2income','PAT to Income'),
                                ('proj2income','Project to Income'),
                                ('expense2income','Expense to Income'),
                                ('proj2pc','Project to Petty Cash Account'),
                                ('income2pc','Income to Petty Cash Account'),
                                ('expense2people','Expense to PAT Account'),
                                ('expense2proj','Expense to Project Account'),
                                ],'Transfer Type'),
        'bank_account':fields.many2one('res.partner.bank','Bank Account'),
        'amount':fields.float('Amount'),
        'currency_id':fields.many2one('res.currency','Currency'),
        'multiple':fields.boolean('Multiple Destination'),
        'distribute_type':fields.selection([
                                ('fixed','Fixed Amount'),
                                ('percentage','Percentage'),
                                ('equal','Equally Distributed'),
                                ],'Distribution Type'),
        'pettycash_id':fields.many2one('account.pettycash', 'Petty Cash Account'),
        'state': fields.selection([
            ('draft','Draft'),
            ('transfer','Transferred'),
            ('cancel','Cancelled'),
            ],'Status', select=True),
        }
    _defaults = {
            'date':lambda *a: time.strftime('%Y-%m-%d'),
            'period_id':_get_period,
            'journal_id':_get_journal,
            'currency_id':'base.PHP',
            'distribute_type':'fixed',
            'state':'draft',
            }
    
    def onchange_multiple(self, cr, uid, ids, multiple=False):
        result = {}
        if multiple:
            for iat in self.read(cr, uid, ids, context=None):
                for iatd_id in iat['pat_iatd_ids']: 
                    self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
            result = {'value':{'dest_pat_analytic_id':False,'dest_proj_analytic_id':False,'distribute_type':False}}
        if not multiple:
            for iat in self.read(cr, uid, ids, context=None):
                for iatd_id in iat['pat_iatd_ids']: 
                    self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
            result = {'value':{'dest_pat_analytic_id':False,'dest_proj_analytic_id':False,'distribute_type':False}}
        return result
    
    def onchange_amount(self, cr, uid, ids, amount=False,distribute_type=False):
        result={}
        new_iatd = []
        iatd_ids = []
        acc_ids = []
        pat_id = False
        proj_id = False
        pat_bool = False
        income_bool = False
        income_id = False
        if amount>0.00:
            for iat in self.read(cr, uid, ids, context=None):
                if distribute_type in ['fixed','percentage']:
                    if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                        iatd_ids = iat['proj_iatd_ids']
                        pat_id = False
                        pat_bool = False
                        proj_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id'])
                            acc_ids.append(iatd_read['proj_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                        iatd_ids = iat['pat_iatd_ids']
                        pat_id = iat['id']
                        proj_id = False
                        pat_bool = True
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id'])
                            acc_ids.append(iatd_read['pat_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                        iatd_ids = iat['income_iatd_ids']
                        pat_id = False
                        proj_id = False
                        pat_bool = False
                        income_bool = True
                        income_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                            acc_ids.append(iatd_read['income_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    for acc_id in acc_ids:
                        proj_analytic = False
                        pat_analytic = False
                        income_analytic = False
                        if pat_bool==False and income_bool==False:
                            pat_analytic = False
                            proj_analytic = acc_id
                        if pat_bool==False and income_bool==True:
                            pat_analytic = False
                            proj_analytic = False
                            income_analytic = acc_id
                        elif pat_bool==True:
                            pat_analytic = acc_id
                            proj_analytic = False
                            income_analytic = False
                        new_iatd_ids = {
                            'proj_analytic_id':proj_analytic,
                            'pat_analytic_id':pat_analytic,
                            'income_analytic_id':income_analytic,
                            'amount':'0.00',
                            'pat_iat_id':pat_id,
                            'proj_iat_id':proj_id,
                            'income_iat_id':income_id,
                            }
                        new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                        new_iatd.append(new_iatd_id)
                    if pat_bool==False and income_bool==False:
                        result = {'value':{'proj_iatd_ids':new_iatd}}
                    if pat_bool==False and income_bool==True:
                        result = {'value':{'income_iatd_ids':new_iatd}}
                    if pat_bool==True:
                        result = {'value':{'pat_iatd_ids':new_iatd}}
                if distribute_type=='equal':
                    if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                        iatd_ids = iat['proj_iatd_ids']
                        pat_id = False
                        pat_bool = False
                        proj_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id', ])
                            acc_ids.append(iatd_read['proj_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                        iatd_ids = iat['pat_iatd_ids']
                        pat_id = iat['id']
                        proj_id = False
                        pat_bool = True
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id', ])
                            acc_ids.append(iatd_read['pat_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                        iatd_ids = iat['income_iatd_ids']
                        pat_id = False
                        proj_id = False
                        pat_bool = False
                        income_bool = True
                        income_id = iat['id']
                        for iatd_id in iatd_ids:
                            iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                            acc_ids.append(iatd_read['income_analytic_id'][0])
                            self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                    dest_len = len(iatd_ids)
                    amt = amount/dest_len
                    ctr=0
                    amt = "%.2f" % amt
                    amt = float(amt)
                    check_amt = amt * dest_len
                    check_amt = "%.2f" % check_amt
                    check_amt = float(check_amt)
                    check_amt = amount - check_amt
                    for acc_id in acc_ids:
                        proj_analytic = False
                        pat_analytic = False
                        income_analytic = False
                        if pat_bool==False and income_bool==False:
                            pat_analytic = False
                            proj_analytic = acc_id
                        if pat_bool==False and income_bool==True:
                            pat_analytic = False
                            proj_analytic = False
                            income_analytic = acc_id
                        elif pat_bool==True:
                            pat_analytic = acc_id
                            proj_analytic = False
                            income_analytic = False
                        if ctr==0:
                            amt = amt + check_amt
                            new_iatd_ids = {
                                'proj_analytic_id':proj_analytic,
                                'pat_analytic_id':pat_analytic,
                                'income_analytic_id':income_analytic,
                                'amount':amt,
                                'pat_iat_id':pat_id,
                                'proj_iat_id':proj_id,
                                'income_iat_id':income_id,
                                }
                            ctr=1
                            new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                            new_iatd.append(new_iatd_id)
                        elif ctr==1:
                            amt = amount/dest_len
                            amt = "%.2f" % amt
                            new_iatd_ids = {
                                'proj_analytic_id':proj_analytic,
                                'pat_analytic_id':pat_analytic,
                                'income_analytic_id':income_analytic,
                                'amount':amt,
                                'pat_iat_id':pat_id,
                                'proj_iat_id':proj_id,
                                'income_iat_id':income_id,
                                }
                            new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                            new_iatd.append(new_iatd_id)
                    if pat_bool==False and income_bool==False:
                        result = {'value':{'proj_iatd_ids':new_iatd}}
                    if pat_bool==False and income_bool==True:
                        result = {'value':{'income_iatd_ids':new_iatd}}
                    if pat_bool==True:
                        result = {'value':{'pat_iatd_ids':new_iatd}}
        return result
    
    def onchange_distribution(self, cr, uid, ids, distribute_type=False,amount=False):
        result={}
        new_iatd = []
        iatd_ids = []
        acc_ids = []
        pat_id = False
        proj_id = False
        income_id = False
        income_bool = False
        pat_bool = False
        if distribute_type in ['fixed','percentage']:
            for iat in self.read(cr, uid, ids, context=None):
                if amount<=0.00:
                    raise osv.except_osv(_('Error !'), _('Please indicate amount!'))
                if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                    iatd_ids = iat['proj_iatd_ids']
                    pat_id = False
                    pat_bool = False
                    proj_id = iat['id']
                    income_bool = False
                    income_id = False
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id'])
                        acc_ids.append(iatd_read['proj_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                    iatd_ids = iat['pat_iatd_ids']
                    pat_id = iat['id']
                    proj_id = False
                    pat_bool = True
                    income_bool = False
                    income_id = False
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id'])
                        acc_ids.append(iatd_read['pat_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                    iatd_ids = iat['income_iatd_ids']
                    pat_id = False
                    proj_id = False
                    pat_bool = False
                    income_bool = True
                    income_id = iat['id']
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                        acc_ids.append(iatd_read['income_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                for acc_id in acc_ids:
                    proj_analytic = False
                    pat_analytic = False
                    income_analytic = False
                    if pat_bool==False and income_bool==False:
                        pat_analytic = False
                        proj_analytic = acc_id
                    if pat_bool==False and income_bool==True:
                        pat_analytic = False
                        proj_analytic = False
                        income_analytic = acc_id
                    elif pat_bool==True:
                        pat_analytic = acc_id
                        proj_analytic = False
                        income_analytic = False
                    new_iatd_ids = {
                        'proj_analytic_id':proj_analytic,
                        'pat_analytic_id':pat_analytic,
                        'income_analytic_id':income_analytic,
                        'amount':'0.00',
                        'pat_iat_id':pat_id,
                        'proj_iat_id':proj_id,
                        'income_iat_id':income_id,
                        }
                    new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                    new_iatd.append(new_iatd_id)
                    if pat_bool==False and income_bool==False:
                        result = {'value':{'proj_iatd_ids':new_iatd}}
                    if pat_bool==False and income_bool==True:
                        result = {'value':{'income_iatd_ids':new_iatd}}
                    if pat_bool==True:
                        result = {'value':{'pat_iatd_ids':new_iatd}}
        if distribute_type=='equal':
            for iat in self.read(cr, uid, ids, context=None):
                if amount<=0.00:
                    raise osv.except_osv(_('Error !'), _('Please indicate amount!'))
                if iat['transfer_type'] in ['people2proj', 'proj2proj','expense2proj']:
                    iatd_ids = iat['proj_iatd_ids']
                    pat_id = False
                    pat_bool = False
                    proj_id = iat['id']
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['proj_analytic_id', ])
                        acc_ids.append(iatd_read['proj_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2people', 'proj2people','expense2people']:
                    iatd_ids = iat['pat_iatd_ids']
                    pat_id = iat['id']
                    proj_id = False
                    pat_bool = True
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['pat_analytic_id', ])
                        acc_ids.append(iatd_read['pat_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                if iat['transfer_type'] in ['people2income', 'proj2income','expense2income']:
                    iatd_ids = iat['income_iatd_ids']
                    pat_id = False
                    proj_id = False
                    pat_bool = False
                    income_bool = True
                    income_id = iat['id']
                    for iatd_id in iatd_ids:
                        iatd_read = self.pool.get('internal.account.transfer.destination').read(cr, uid, iatd_id, ['income_analytic_id'])
                        acc_ids.append(iatd_read['income_analytic_id'][0])
                        self.pool.get('internal.account.transfer.destination').unlink(cr, uid, iatd_id)
                dest_len = len(iatd_ids)
                amt = amount/dest_len
                ctr=0
                amt = "%.2f" % amt
                amt = float(amt)
                check_amt = amt * dest_len
                check_amt = "%.2f" % check_amt
                check_amt = float(check_amt)
                check_amt = amount - check_amt
                for acc_id in acc_ids:
                    proj_analytic = False
                    pat_analytic = False
                    income_analytic = False
                    if pat_bool==False and income_bool==False:
                        pat_analytic = False
                        proj_analytic = acc_id
                    if pat_bool==False and income_bool==True:
                        pat_analytic = False
                        proj_analytic = False
                        income_analytic = acc_id
                    elif pat_bool==True:
                        pat_analytic = acc_id
                        proj_analytic = False
                        income_analytic = False
                    if ctr==0:
                        amt = amt + check_amt
                        new_iatd_ids = {
                            'proj_analytic_id':proj_analytic,
                            'pat_analytic_id':pat_analytic,
                            'income_analytic_id':income_analytic,
                            'amount':amt,
                            'pat_iat_id':pat_id,
                            'proj_iat_id':proj_id,
                            'income_iat_id':income_id,
                            }
                        ctr=1
                        new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                        new_iatd.append(new_iatd_id)
                    elif ctr==1:
                        amt = amount/dest_len
                        amt = "%.2f" % amt
                        new_iatd_ids = {
                            'proj_analytic_id':proj_analytic,
                            'pat_analytic_id':pat_analytic,
                            'income_analytic_id':income_analytic,
                            'amount':amt,
                            'pat_iat_id':pat_id,
                            'proj_iat_id':proj_id,
                            'income_iat_id':income_id,
                            }
                        new_iatd_id = self.pool.get('internal.account.transfer.destination').create(cr, uid, new_iatd_ids)
                        new_iatd.append(new_iatd_id)
                if pat_bool==False and income_bool==False:
                    result = {'value':{'proj_iatd_ids':new_iatd}}
                if pat_bool==False and income_bool==True:
                    result = {'value':{'income_iatd_ids':new_iatd}}
                if pat_bool==True:
                    result = {'value':{'pat_iatd_ids':new_iatd}}
        return result
    
    def create(self, cr, uid, vals, context=None):
        if 'transfer_type' in context:
            if context['transfer_type']=='people2proj':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2proj'),
                })
            if context['transfer_type']=='proj2people':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2people'),
                })
            if context['transfer_type']=='people2pc':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2pc'),
                })
            if context['transfer_type']=='proj2pc':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2pc'),
                })
            if context['transfer_type']=='income2pc':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.income2pc'),
                })
            if context['transfer_type']=='people2people':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2people'),
                })
            if context['transfer_type']=='proj2proj':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2proj'),
                })
            if context['transfer_type']=='people2income':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.people2income'),
                })
            if context['transfer_type']=='proj2income':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.proj2income'),
                })
            if context['transfer_type']=='expense2income':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.expense2income'),
                })
            if context['transfer_type']=='expense2people':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.expense2people'),
                })
            if context['transfer_type']=='expense2proj':
                vals.update({
                'name': self.pool.get('ir.sequence').get(cr, uid, 'iat.expense2proj'),
                })
                
        return super(internal_account_transfer, self).create(cr, uid, vals, context)

internal_account_transfer()

class internal_account_transfer_destination(osv.osv):
    _name = 'internal.account.transfer.destination'
    _description = 'Internal Account Transfer Destinations'
    _columns = {
        'name':fields.char('Account Name',size=64),
        'pat_analytic_id':fields.many2one('account.analytic.account','Analytic Account',domain=[('supplier','=',True)]),
        'proj_analytic_id':fields.many2one('account.analytic.account','Analytic Account',domain=[('project','=',True)]),
        'amount':fields.float('Amount/Percentage', digits_compute=dp.get_precision('Account')),
        'proj_iat_id':fields.many2one('internal.account.transfer','Transfer ID',ondelete='cascade'),
        'pat_iat_id':fields.many2one('internal.account.transfer','Transfer ID',ondelete='cascade'),
        'income_iat_id':fields.many2one('internal.account.transfer','Transfer ID', ondelete='cascade'),
        'expense_iat_id':fields.many2one('internal.account.transfer','Transfer ID', ondelete='cascade'),
        'income_analytic_id':fields.many2one('account.analytic.account','Analytic Account',domain=[('ntm_type','=','income')]),
        'remarks':fields.text('Remarks'),
        'percentage':fields.float('Percentage(%)'),
        'percentage_bool':fields.boolean('Percentage?'),
        }
    
    def onchange_percentage(self,cr, uid, ids, percentage=False):
        result = {}
        if percentage:
            amount = 0.00
            for iatd in self.read(cr, uid, ids, context=None):
                if iatd['proj_iat_id']:
                    iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['proj_iat_id'][0],['amount'])
                    amount = iat_read['amount']
                elif iatd['pat_iat_id']:
                    iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['pat_iat_id'][0],['amount'])
                    amount=iat_read['amount']
            amount = (amount * percentage) / 100
            result = {'value':{
                'amount':amount,
                }
            }
        return result 
    
    def write(self,cr, uid,ids,vals, context=None):
        if 'percentage' in vals:
            amount = 0.00
        if vals['percentage']>0.00:
                for iatd in self.read(cr, uid, ids, context=None):
                    if iatd['proj_iat_id']:
                        iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['proj_iat_id'][0],['amount'])
                        amount = iat_read['amount']
                    elif iatd['pat_iat_id']:
                        iat_read = self.pool.get('internal.account.transfer').read(cr, uid, iatd['pat_iat_id'][0],['amount'])
                        amount=iat_read['amount']
                amount = (amount * vals['percentage']) / 100
                vals['amount']=amount
        elif vals['percentage']<1.00:
            vals['amount']=vals['amount']
        return super(internal_account_transfer_destination,self).write(cr, uid,ids, vals,context=None)
                    
                
    
internal_account_transfer_destination()


class pcdenom(osv.osv):
    _inherit = 'pettycash.denom'
    _columns = {
        'iat_id':fields.many2one('internal.account.transfer','IAT ID', ondelete='cascade'),
        }
pcdenom()

class iat(osv.osv):
    _inherit = 'internal.account.transfer'
    _columns = {
        'pat_iatd_ids':fields.one2many('internal.account.transfer.destination','pat_iat_id','Destinations'),
        'proj_iatd_ids':fields.one2many('internal.account.transfer.destination','proj_iat_id','Destinations'),
        'income_iatd_ids':fields.one2many('internal.account.transfer.destination','income_iat_id','Destinations'),
        'denom_ids':fields.one2many('pettycash.denom','iat_id','Denominations'),
        'move_id':fields.many2one('account.move','Journal Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Releasing Journal Items', readonly=True),
        }
    
    def onchange_curr(self, cr, uid, ids, currency_id=False):
        result = {}
        if currency_id:
            for iat in self.read(cr, uid, ids, context=None):
                if iat['transfer_type']=='people2pc':
                    result = {'value':{'pettycash_id':False}}
        return result
    
    def onchange_pcid(self, cr, uid, ids, pettycash_id=False, context=None):
        result = {}
        if pettycash_id:
            iat_ids = ids
            iat_id = iat_ids[0]
            pc_read = self.pool.get('account.pettycash').read(cr,uid, pettycash_id, ['currency_id'])
            denom_search = self.pool.get('denominations').search(cr, uid, [('currency_id','=',pc_read['currency_id'][0])])
            currency = pc_read['currency_id'][1]
            if not denom_search:
                raise osv.except_osv(_('Error!'), _('%s has no available denominations.Please add them!')%currency)
            elif denom_search:
                denominations = []
                denom_del = self.pool.get('pettycash.denom').search(cr, uid, [('iat_id','=',iat_id)])
                self.pool.get('pettycash.denom').unlink(cr, uid, denom_del)
                for denom in denom_search:
                    vals = {
                        'name':denom,
                        'iat_id':iat_id,
                        }
                    newd = self.pool.get('pettycash.denom').create(cr, uid, vals)
                    denominations.append(newd)
                result = {'values':{'denom_ids':denominations}}
            return result
    def transfer(self, cr, uid, ids, context=None):
        if 'transfer_type' in context:
            if context['transfer_type']=='people2pc':
                self.check_denoms(cr, uid, ids)
            if context['transfer_type']=='proj2pc':
                self.check_denoms(cr, uid, ids)
            if context['transfer_type']=='income2pc':
                self.check_denoms(cr, uid, ids)
            if context['transfer_type'] in ['people2income','proj2income','expense2income',
                                            'expense2people','expense2proj',
                                            'proj2proj','people2people','proj2people','people2proj']:
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
            if iat['transfer_type']=='people2income':
                src_account=iat['src_pat_analytic_id'][0]
                dest_account = iat['dest_income_analytic_id'][0]
            if iat['transfer_type']=='proj2income':
                src_account=iat['src_proj_analytic_id'][0]
                dest_account = iat['dest_income_analytic_id'][0]
            if iat['transfer_type']=='expense2income':
                src_account=iat['src_expense_analytic_id'][0]
                dest_account = iat['dest_income_analytic_id'][0]
            if iat['transfer_type']=='expense2people':
                src_account = iat['src_expense_analytic_id'][0]
                dest_account = iat['dest_pat_analytic_id'][0]
            if iat['transfer_type']=='expense2proj':
                src_account = iat['src_expense_analytic_id'][0]
                dest_account = iat['dest_proj_analytic_id'][0]
            if src_account==dest_account:
                raise osv.except_osv(_('Error !'), _('Source and destination accounts must not be the same!'))
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
                        'name':'Destination Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':dest_analytic_read['normal_account'][0],
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
                        'name':'Source Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':src_analytic_read['normal_account'][0],
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
            if iat['transfer_type']=='people2income':
                src_account = iat['src_pat_analytic_id'][0]
                dest_account = iat['income_iatd_ids']
            if iat['transfer_type']=='proj2income':
                src_account = iat['src_proj_analytic_id'][0]
                dest_account = iat['income_iatd_ids']
            if iat['transfer_type']=='expense2income':
                src_account = iat['src_expense_analytic_id'][0]
                dest_account = iat['income_iatd_ids']
            if iat['transfer_type']=='expense2people':
                src_account = iat['src_expense_analytic_id'][0]
                dest_account = iat['pat_iatd_ids']
            if iat['transfer_type']=='expense2proj':
                src_account = iat['src_expense_analytic_id'][0]
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
                if iat['transfer_type'] in ['people2people','proj2people','expense2people']:
                    dest_acc = iatd_read['pat_analytic_id'][0]
                if iat['transfer_type'] in ['people2proj','proj2proj','expense2proj']:
                    dest_acc = iatd_read['proj_analytic_id'][0]
                if iat['transfer_type'] in ['people2income','proj2income','expense2income']:
                    dest_acc = iatd_read['income_analytic_id'][0]
                dest_analytic_read = self.pool.get('account.analytic.account').read(cr, uid, dest_acc,context=None)
                amount = iatd_read['amount'] / rate
                move_line = {
                        'name':'Destination Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':dest_analytic_read['normal_account'][0],
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
                        'name':'Source Account',
                        'journal_id':journal_id,
                        'period_id':period_id,
                        'account_id':src_analytic_read['normal_account'][0],
                        'debit':iat['amount'],
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
iat()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,