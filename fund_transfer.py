import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class fund_transfer(osv.osv):
    _name = 'fund.transfer'
    _description = "Fund Transfers"
    _columns = {
        'name':fields.char('Transfer ID',size=64),
        'type':fields.selection([
                                 ('b2b','Bank to Bank'),
                                 ('a2a','Analytic to Analytic'),
                                 ('p2b','Petty Cash to Bank')
                                 ],'Type'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'src_account':fields.many2one('account.account','Source Bank Account'),
        'pettycash_id':fields.many2one('account.pettycash','Petty Cash Account'),
        'amount':fields.float('Amount to Transfer'),
        'dest_account':fields.many2one('account.account','Destination Bank Account'),
        'src_analytic_account':fields.many2one('account.analytic.account','Source Analytic Account'),
        'dest_analytic_account':fields.many2one('account.analytic.account','Destination Analytic Account'),
        }
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