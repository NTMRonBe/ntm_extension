import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
import tools
import wizard
from tools.translate import _
import os

class region_report(osv.osv):
    _name = 'region.report'
    _description = "Regional Reports"
    _columns = {
        'name':fields.char('Region Name',size=64),
        'period_id':fields.many2one('account.period','Report Period'),
        'gl_acc':fields.many2one('account.analytic.account','Gain Loss Account'),
        'gl_mtd':fields.float('Gain Loss (MTD)'),
        'gl_ytd':fields.float('Gain Loss (YTD)'),
        }
region_report()

class region_report_account(osv.osv):
    _name = 'region.report.account'
    _description = "Accounts"
    _columns = {
        'name':fields.many2one('account.analytic.account','Account'),
        'beg_balance_equity':fields.float('Beginning Balance'),
        'mtd':fields.float('Month to Date'),
        'ytd':fields.float('Year to Date'),
        'income_id':fields.many2one('region.report','Regional Report ID', ondelete='cascade'),
        'expense_id':fields.many2one('region.report','Regional Report ID', ondelete='cascade'),
        'equity_id':fields.many2one('region.report','Regional Report ID', ondelete='cascade'),
        }
region_report_account()

class region_report2(osv.osv):
    _inherit= 'region.report'
    _columns = {
        'income_ids':fields.one2many('region.report.account','income_id','Income Accounts'),
        'expense_ids':fields.one2many('region.report.account','expense_id','Expense Accounts'),
        'equity_ids':fields.one2many('region.report.account','equity_id','Equity Accounts'),
        }
region_report2()

class region_report_wiz(osv.osv_memory):
    _name = 'region.report.wiz'
    _columns = {
    'region_id':fields.many2one('region.config','Region', required=True),
    'period_id':fields.many2one('account.period','Report Period', required=True),
    'date':fields.date('Report Date', required=True),
    }
    def generate(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            region=form['region_id']
            regionRead = self.pool.get('region.config').read(cr, uid, region, ['name', 'income_ids','expense_ids','gain_loss_acct'])
            name = regionRead['name']
            periodRead = self.pool.get('account.period').read(cr, uid, form['period_id'], ['date_start','date_stop', 'fiscalyear_id'])
            start = periodRead['date_start']
            stop = periodRead['date_stop']
            searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',stop),('date','>=',start),('account_id','=',regionRead['gain_loss_acct'][0])])
            total_amount = 0.00
            for entry in searchEntries:
                entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                total_amount +=entryRead['amount']
            fiscalRead = self.pool.get('account.fiscalyear').read(cr, uid, periodRead['fiscalyear_id'][0],['date_start','date_stop'])
            fstart = fiscalRead['date_start']
            fstop = fiscalRead['date_stop']
            searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',fstop),('date','>=',fstart),('account_id','=',regionRead['gain_loss_acct'][0])])
            ftotal_amount = 0.00
            for entry in searchEntries:
                entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                ftotal_amount +=entryRead['amount']
            vals ={
                'period_id':form['period_id'],
                'name':name,
                'gl_acc':regionRead['gain_loss_acct'][0],
                'gl_mtd':total_amount,
                'gl_ytd':ftotal_amount,
            }
            
            report_id = self.pool.get('region.report').create(cr, uid, vals)
            for income in regionRead['income_ids']:
                searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',stop),('date','>=',start),('account_id','=',income)])
                itotal_amount = 0.00
                for entry in searchEntries:
                    entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                    itotal_amount +=entryRead['amount']
                searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',fstop),('date','>=',fstart),('account_id','=',income)])
                iftotal_amount = 0.00
                for entry in searchEntries:
                    entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                    iftotal_amount +=entryRead['amount']
                vals2 = {
                    'name':income,
                    'income_id':report_id,
                    'mtd':itotal_amount,
                    'ytd':iftotal_amount,
                    }
                self.pool.get('region.report.account').create(cr, uid, vals2)
            for expense in regionRead['expense_ids']:
                searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',stop),('date','>=',start),('account_id','=',expense)])
                itotal_amount = 0.00
                for entry in searchEntries:
                    entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                    itotal_amount +=entryRead['amount']
                searchEntries = self.pool.get('account.analytic.line').search(cr, uid, [('date','<=',fstop),('date','>=',fstart),('account_id','=',expense)])
                iftotal_amount = 0.00
                for entry in searchEntries:
                    entryRead=self.pool.get('account.analytic.line').read(cr, uid, entry, ['amount'])
                    iftotal_amount +=entryRead['amount']
                vals2 = {
                    'name':expense,
                    'expense_id':report_id,
                    'mtd':itotal_amount,
                    'ytd':iftotal_amount,
                    }
                self.pool.get('region.report.account').create(cr, uid, vals2)
        return {'type': 'ir.actions.act_window_close'}
region_report_wiz()

class region_budget_wiz(osv.osv_memory):
    _name = 'region.budget.wiz'
    _columns = {
    'region_id':fields.many2one('region.config','Region', required=True),
    'fiscal_id':fields.many2one('account.fiscalyear','Fiscal Year', required=True),
    'income_position':fields.many2one('account.budget.post','Income Budget Position', required=True),
    'expense_position':fields.many2one('account.budget.post','Expense Budget Position', required=True),
    }
    def generate(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            regionRead = self.pool.get('region.config').read(cr, uid, form['region_id'],['name','income_ids','expense_ids'])
            fiscalRead = self.pool.get('account.fiscalyear').read(cr, uid, form['fiscal_id'], ['date_start','date_stop','name'])
            date_start = fiscalRead['date_start']
            date_stop = fiscalRead['date_stop']
            name = regionRead['name']+' '+fiscalRead['name']
            budgetVals = {
                    'name':name,
                    'date_from':date_start,
                    'date_to':date_stop,
                    'code':name,
                    }
            budgetID = self.pool.get('crossovered.budget').create(cr, uid, budgetVals)
            for income in regionRead['income_ids']:
                budgetLine = {
                    'analytic_account_id':income,
                    'general_budget_id':form['income_position'],
                    'date_from':date_start,
                    'date_to':date_stop,
                    'planned_amount':0.00,
                    'crossovered_budget_id':budgetID,
                    }
                self.pool.get('crossovered.budget.lines').create(cr, uid, budgetLine)
            for expense in regionRead['expense_ids']:
                budgetLine = {
                    'analytic_account_id':expense,
                    'general_budget_id':form['expense_position'],
                    'date_from':date_start,
                    'date_to':date_stop,
                    'planned_amount':0.00,
                    'crossovered_budget_id':budgetID,
                    }
                self.pool.get('crossovered.budget.lines').create(cr, uid, budgetLine)
        return {'type': 'ir.actions.act_window_close'}
region_budget_wiz()

class account_period(osv.osv):
    _inherit = 'region.config'
    
    def budget(self, cr, uid, ids, context=None):
        for period in self.read(cr, uid, ids, context=None):
            period_id = period['id']
        return {
            'name': 'Create Budget',
            'view_type':'form',
            'nodestroy': True,
            'target': 'new',
            'view_mode':'form',
            'res_model':'region.budget.wiz',
            'type':'ir.actions.act_window',
            'context':{'default_region_id':period_id},}
account_period()