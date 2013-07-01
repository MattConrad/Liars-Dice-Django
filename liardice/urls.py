from django.conf.urls.defaults import *

urlpatterns = patterns('ldsite.liardice.views',
    (r'^$', 'current_game'),
    (r'^open_or_new_games/$', 'open_or_new_games'),
    (r'^set_nickname/$', 'set_nickname'),
    (r'^new_session/$', 'new_session'),
    (r'^x_check_for_updates/$', 'x_check_for_updates'),
    (r'^x_get_open_games/$', 'x_get_open_games'),
    (r'^x_join_game/(?P<game_id>\d+)/$', 'x_join_game'),
    (r'^x_update_round/$', 'x_update_round'),
    (r'^x_update_game/$', 'x_update_game'),
    (r'^x_send_bid/(?P<dice_count>\d+)/(?P<pips>\d+)/$', 'x_send_bid'),
    (r'^x_send_challenge/$', 'x_send_challenge'),
)    
        
