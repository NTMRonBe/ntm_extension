# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
from tools.translate import _
from dbfpy import dbf
import csv
import sys
import netsvc

class dbf_reader(osv.osv_memory):
    _name = "dbf.reader"
    _description = "DBF Reader"
    _columns = {
        'filename': fields.char('File Name',size=64),
    }
    
    def convert(self, cr, uid, ids, context=None):
        user_pool = self.pool.get('res.users')
        for form in self.read(cr, uid, ids, context=context):
            if form['filename']:
                file_name = form['filename']
                user_id = uid
                netsvc.Logger().notifyChannel("filename", netsvc.LOG_INFO, ' '+str(file_name))
                netsvc.Logger().notifyChannel("User", netsvc.LOG_INFO, ' '+str(user_id))
                for users in user_pool.browse(cr, uid, [user_id]):
                    user_name = users.name
                    location = users.location
                    location_filename = location + '/' + file_name + '.dbf'
                    new_csv = '/var/log/openerp/files' + '/' + file_name + '.csv'
                    netsvc.Logger().notifyChannel("User", netsvc.LOG_INFO, ' '+str(user_name))
                    netsvc.Logger().notifyChannel("Location", netsvc.LOG_INFO, ' '+str(location))
                    netsvc.Logger().notifyChannel("Actual File", netsvc.LOG_INFO, ' '+str(location_filename))
                    in_db = dbf.Dbf(location_filename)
                    out_csv = csv.writer(open(new_csv,'wb'))
                    names = []
                    for field in in_db.header.fields:
                        names.append(field.name)
                    out_csv.writerow(names)
                    
                    for rec in in_db:
                        out_csv.writerow(rec.fieldData)
                        
                    in_db.close
        return {'type': 'ir.actions.act_window_close'}

dbf_reader()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

