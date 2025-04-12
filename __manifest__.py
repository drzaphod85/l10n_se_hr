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
        'base'
        'hr',
        'hr_payroll',
        'hr_holidays',
        'hr_attendance',
    ],
    'data': [
            'security/ir.model.access.csv',
            # Region and Municipality data
            'data/l10n_se_hr_regions.xml',
            'data/municipalities/l10n_se_hr_municipalities_01.xml',
            'data/municipalities/l10n_se_hr_municipalities_03.xml',
            'data/municipalities/l10n_se_hr_municipalities_04.xml',
            'data/municipalities/l10n_se_hr_municipalities_05.xml',
            'data/municipalities/l10n_se_hr_municipalities_06.xml',
            'data/municipalities/l10n_se_hr_municipalities_07.xml',
            'data/municipalities/l10n_se_hr_municipalities_08.xml',
            'data/municipalities/l10n_se_hr_municipalities_09.xml',
            'data/municipalities/l10n_se_hr_municipalities_10.xml',
            'data/municipalities/l10n_se_hr_municipalities_12.xml',
            'data/municipalities/l10n_se_hr_municipalities_13.xml',
            'data/municipalities/l10n_se_hr_municipalities_14.xml',
            'data/municipalities/l10n_se_hr_municipalities_17.xml',
            'data/municipalities/l10n_se_hr_municipalities_18.xml',
            'data/municipalities/l10n_se_hr_municipalities_19.xml',
            'data/municipalities/l10n_se_hr_municipalities_20.xml',
            'data/municipalities/l10n_se_hr_municipalities_21.xml',
            'data/municipalities/l10n_se_hr_municipalities_22.xml',
            'data/municipalities/l10n_se_hr_municipalities_23.xml',
            'data/municipalities/l10n_se_hr_municipalities_24.xml',
            'data/municipalities/l10n_se_hr_municipalities_25.xml',
            # Municipality tax update scheduler
            'data/ir_cron_tax_update.xml',
            # Other data files
            'data/l10n_se_hr_leave_types_data.xml',
            'data/l10n_se_hr_salary_rules_data.xml',
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