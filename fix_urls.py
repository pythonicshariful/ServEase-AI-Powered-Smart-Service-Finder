import os
import re

bp_map = {
    'provider_dashboard': 'provider.dashboard',
    'finder_dashboard': 'finder.dashboard',
    'finder_profile': 'finder.profile',
    'create_post': 'finder.create_post',
    'user_profile': 'core.user_profile',
    'provider_best_matches': 'provider.best_matches',
    'add_skill': 'provider.add_skill',
    'provider_profile': 'provider.profile',
    'dashboard': 'core.dashboard',
    'delete_account': 'core.delete_account',
    'view_profile': 'core.view_profile',
    'home': 'core.home',
    'register': 'auth.register',
    'login': 'auth.login',
    'logout': 'auth.logout',
}

for root, _, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            for old, new in bp_map.items():
                content = re.sub(rf"url_for\(['\"]{old}['\"]", f"url_for('{new}'", content)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
print('Done!')
