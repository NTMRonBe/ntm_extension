# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import fields, osv

class ntm_installer(osv.osv_memory):
    _name = 'ntm.installer'
    _inherit = 'res.config.installer'
    _columns = {
        'group_ids':fields.many2many('res.groups','installer_id','ntm_id','ntm_group_rel', 'Groups to Remove'),
        }
    
    def removeGroups(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=None):
            for group in form['group_ids']:
                print group
                groupReader = self.pool.get('res.groups').read(cr, uid, group, context=None)
                print groupReader
                for model in groupReader['model_access']:
                    self.pool.get('ir.model.access').unlink(cr, uid, model)
                cr.execute('delete from res_groups where id=%s' % group)
        return True
ntm_installer()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
