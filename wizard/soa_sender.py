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
import sys
import netsvc
import smtplib

import os
 
from email import Encoders
from email.MIMEBase import MIMEBase
from email.MIMEMultipart import MIMEMultipart
from email.Utils import formatdate

class soa_sender(osv.osv_memory):
    _name = "soa.sender"
    _description = "SOA Sender"
    _columns = {
        'filename': fields.char('File Name',size=64),
        'username': fields.char('Username',size=64),
        'password':fields.char('Password',size=64),
    }
    
    def convert(self, cr, uid, ids, context=None):
        user_pool = self.pool.get('res.users')
        for form in self.read(cr, uid, ids, context=context):
            if form['filename']:
                file_name = form['filename']
                login = form['username']
                #login = "\"" + login + "\""
                password = form['password']
                #password = "\"" + password + "\""
                user_id = uid
                message = "This is a test message from SOA Sender"
                netsvc.Logger().notifyChannel("Login", netsvc.LOG_INFO, ' '+str(login))
                #netsvc.Logger().notifyChannel("Password", netsvc.LOG_INFO, ' '+str(password))
                for users in user_pool.browse(cr, uid, [user_id]):
                    user_name = users.name
                    location = users.location
                    location_filename = location + '/' + file_name + '.txt'
                    f = open (location_filename,'r')
                    answer = ""
                    for line in f:
                 #       netsvc.Logger().notifyChannel("Line", netsvc.LOG_INFO, ' '+str(line.strip()))
                        if len(answer)>0:
                            answer = answer +', '+ line.strip()
                        else:
                            answer = line.strip() 
                    f.close()
                    send_to = "\"" + answer + "\""
                    netsvc.Logger().notifyChannel("Line", netsvc.LOG_INFO, ' '+str(send_to))
                    server = smtplib.SMTP_SSL('smtp.gmail.com',587)
                    subject = file_name
                    headers = ["From: " + login,
                               "Subject: " + subject,
                               "To: " + send_to,
                               "MIME-Version: 1.0",
                               "Content-Type: text/html"]
                    headers = "\r\n".join(headers)
                    server.set_debuglevel(1)
                    server.ehlo
                    server.login(login,password)
                    login = "\"" + login + "\"" 
                    server.sendmail(login,answer,headers + "\r\n\r\n",message)
                    server.quit()
        return {'type': 'ir.actions.act_window_close'}

soa_sender()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

