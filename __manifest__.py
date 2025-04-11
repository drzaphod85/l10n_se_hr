{
    'name': 'Swedish HR Localization',
    'version': '1.0',
    'category': 'Human Resources/Localization',
    'summary': 'Swedish HR rules and regulations',
    'description': """
Swedish HR Localization
=======================
This module adds Swedish-specific HR functionality:
- Personal identity number (personnummer) validation
- Municipality and region data
- Swedish tax calculations
- Vacation management (semesterrätt)
- Sick leave handling with karensdag
- Overtime tracking 
- Parental leave management
- Integration with Swedish regulations
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'hr',
        'hr_payroll',
        'hr_holidays',
        'hr_attendance',
    ],
    'data': [
            'security/ir.model.access.csv',
            # Region and Municipality data
            'data/l10n_se_hr_regions.xml',
            'data/l10n_se_hr_municipalities_data.xml',
            # Municipality tax update scheduler
            'data/ir_cron_tax_update.xml',
            # Other data files
            'data/leave_types.xml',
            'data/salary_rules.xml',
            'data/ir_cron.xml',
            'data/website_pages.xml',
            # Views
            'views/hr_employee_views.xml',
            'views/hr_leave_views.xml',
            'views/hr_overtime_views.xml',
            'views/menu_items.xml',
            'views/municipality_menu.xml',
            'views/region_municipality_views.xml',
            'views/tax_table_views.xml',
            'views/vacation_statement_report.xml',
            'views/parental_leave_report_views.xml',
        ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}