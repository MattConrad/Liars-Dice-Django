from django.shortcuts import render_to_response, get_object_or_404
from django.http import (HttpResponse, HttpResponseNotFound, 
        HttpResponseBadRequest, HttpResponseRedirect)
from django.core.urlresolvers import reverse
from forms import NewGameForm
from models import Game, Player
from django.views.generic.simple import direct_to_template
from django.utils import simplejson
import re

def current_game(request):
    game_id = request.session.get('game_id', None)
    try: 
        game = Game.objects.get(pk=game_id)
        return render_to_response('current_game.html', {'game': game})
    except Game.DoesNotExist:
        return HttpResponseRedirect(reverse(open_or_new_games))

def new_session(request):
    request.session['game_id'] = None
    request.session['player_id'] = None
    return HttpResponseRedirect(reverse(open_or_new_games))

#open games stuff is now handled via JSON, just process new games here.
def open_or_new_games(request):
    if not request.COOKIES.get('nickname', ''):
        return HttpResponseRedirect(reverse(set_nickname))

    if request.method == 'POST':
        form = NewGameForm(request.POST)
        if form.is_valid():
            nickname = re.sub(r'\W', '', request.COOKIES.get('nickname', ''))
            num_players = form.cleaned_data['number_of_players']
            game = Game(name=nickname, num_players=num_players)
            game.save()
            try:
                player = game.add_player(nickname, True)
                request.session['player_id'] = player.id
                request.session['game_id'] = game.id
            except Game.InvalidPlayer as x:
                pass
                #TODO: add session error message

            return HttpResponseRedirect(reverse(current_game))
    else:
        form = NewGameForm()

    return direct_to_template(request, 
            'open_or_new_games.html', {'form': form })

def set_nickname(request):
    if request.method == 'POST':
        nickname = re.sub(r'\W', '', request.POST['nickname'])
        if nickname:
            response = HttpResponseRedirect(reverse(open_or_new_games))
            response.set_cookie('nickname', nickname, max_age=365*24*60*60)
            return response

    return direct_to_template(request, 'set_nickname.html')

def x_send_bid(request, dice_count, pips):
    game_id = request.session.get('game_id', None)
    player_id = request.session.get('player_id', None)
    try: 
        game = Game.objects.get(pk=game_id)
        game.apply_bid(player_id, int(dice_count), int(pips));
        return HttpResponse()
    except Exception as x:
        print x
        return HttpResponseBadRequest('Attempt to send bid failed.')

def x_send_challenge(request):
    game_id = request.session.get('game_id', None)
    player_id = request.session.get('player_id', None)
    try: 
        game = Game.objects.get(pk=game_id)
        game.apply_challenge(player_id);
        return HttpResponse()
    except Exception as x:
        print x
        return HttpResponseBadRequest('Attempt to send challenge failed.')

def x_get_open_games(request):
    # maybe there should be an analog to x_check_for_updates?
    lod = Game.open_games.get_open_games_listing()
    if lod:
        max_game_id = max([gd['id'] for gd in lod])
    else:
        max_game_id = 0
    result = {'openGames': lod, 'maxGameID': max_game_id}
    return HttpResponse(simplejson.dumps(result))

def x_check_for_updates(request):
    game_id = request.session.get('game_id', None)
    try: 
        game = Game.objects.get(pk=game_id)
        result = {'gameRound': game.game_round_ctr, 
                'roundStatus': game.round_status_ctr}
        return HttpResponse(simplejson.dumps(result))
    except Game.DoesNotExist:
        return HttpResponseNotFound('User session does not match any game.')

def x_join_game(request, game_id):
    if not request.COOKIES.get('nickname', ''):
        return HttpResponseBadRequest(
                'Corrupted nickname, use Ctrl-F5 to reload.') 

    game = Game.objects.get(pk=game_id)
    nickname = re.sub(r'\W', '', request.COOKIES.get('nickname', ''))
    try:
        player = game.add_player(nickname, True)
        request.session['player_id'] = player.id
        request.session['game_id'] = game.id
        return HttpResponse()
    except Game.InvalidPlayer as x:
        return HttpResponseBadRequest('Join game denied: ' + x.value)

def x_update_game(request): 
    game_id = request.session.get('game_id', None)
    player_id = request.session.get('player_id', None)
    try: 
        game = Game.objects.get(pk=game_id)
        #'others_die_count' (dict, player_name/dice_count) 
        # and 'request_player_dice' (list of dice)
        result = game.get_game_summary_dict(player_id)

        return HttpResponse(simplejson.dumps(result))
    except Game.DoesNotExist:
        return HttpResponseNotFound('User session does not match any game.')

def x_update_round(request): 
    result = {}
    game_id = request.session.get('game_id', None)
    player_id = request.session.get('player_id', None)
    try: 
        game = Game.objects.get(pk=game_id)
        if game.game_round_ctr == 0:
            msgs = []
            msgs.append(['std', 'Players joined: ' + 
                    ', '.join(game.get_joined_player_names())])
            msgs.append(['std', 'Waiting for ' 
                    + str(game.get_unjoined_player_count()) + ' more.'])
            #TODO: hardcoding these is kind of a mess, bc i have to maintain changes here...
            result['roundMessages'] = msgs 
            result['lastBidDice'] = 0
            result['lastBidPips'] = 0
            result['isYourTurn'] = False 
            result['isGameActive'] = True 
        else:
            result = game.get_round_summary_dict(player_id)
        return HttpResponse(simplejson.dumps(result))
    except Game.DoesNotExist:
        return HttpResponseNotFound('User session does not match any game.')



