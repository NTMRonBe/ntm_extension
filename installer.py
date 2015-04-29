import os
import fnmatch
from shutil import copytree, rmtree, ignore_patterns, copy
import subprocess
import sys
from datetime import datetime

openerp_dir = '/media/sf_from-macbook/eclipse-workspace/'
module_name = 'ntm_extension'
loan_module_dir = openerp_dir + module_name
tmp_loan_module_dir = '/tmp/' + module_name
now = datetime.today()
orig_installer_name = '/install-' + module_name + '.run'
installer_name = '/install-' + module_name + '-' + now.strftime('%Y%m%d%H%M') + '.run'

# initial check for our temp environment, delete if existing
if os.path.isdir(tmp_loan_module_dir):
    rmtree(tmp_loan_module_dir)

if os.path.isfile(loan_module_dir + '/install*.run'):
    os.remove(loan_module_dir + '/install*.run')

# work on the temp copy
print "-> Creating temporary files..."
copytree(loan_module_dir, tmp_loan_module_dir, 
         ignore=ignore_patterns(*('installer.py', '*.pyc','*.doc', '*.docx', 
                                '*.sql', '*.pyc', '*.run', '*.gz', 
                                '*.zip', '*.sh', '*.pdf', '.project', '.pydevproject', '.git')))

print "Generating installer..."
try: 
    subprocess.check_output('which makeself',shell=True)
except: 
    rmtree(tmp_loan_module_dir)
    sys.exit('ERROR: A required binary was not found. Try installing it by\
                                        running: sudo apt-get install makeself')

subprocess.check_output(['/usr/bin/python', '-m', 'compileall', tmp_loan_module_dir])

#we only need the important files e.g. xml, jrxml
exclude_dirs =['migration_scripts', 'send_sms_android']
 
for root, dirs, files in os.walk(tmp_loan_module_dir):
    if root.split('/')[-1] in exclude_dirs:
        rmtree(root)
        continue
    
    for basename in files:
        if fnmatch.fnmatch(basename, '*'):
            filename = os.path.join(root, basename)
            if (filename.endswith(('__init__.py', '__openerp__.py'))):
                continue 
            
            if filename.endswith(('.py')):
                os.remove(filename)

subprocess.check_output("/usr/bin/makeself --notemp %s %s \
       \"NTM Extensions\" echo \"Done.\"" % (tmp_loan_module_dir, \
       loan_module_dir + installer_name), shell=True)

# cleanup
print "-> Removing temporary files.."
rmtree(tmp_loan_module_dir)
print "-> Installer creation successful. Location: %s" \
          % loan_module_dir + installer_name

copy(loan_module_dir + installer_name, loan_module_dir + orig_installer_name)