from django.db import models
from django.forms.models import model_to_dict
from django.db.models import Count 
from datetime import datetime
import random
import re
from liardice import get_text_from_dice_and_pips

class OpenGameManager(models.Manager):
    def get_open_games_objects(self):
        return [g for g in Game.objects.filter(is_active=True) 
            if g.get_unjoined_player_count() > 0]

    #returns list of dictionaries with keys: 'id', 'listing_text'
    def get_open_games_listing(self):
        lod = []
        for g in self.get_open_games_objects():
            d = {}
            d['id'] = g.id
            d['listing_text'] = g.get_game_listing_text()
            lod.append(d)
        return lod

# Create your models here.
class Game(models.Model):
    name = models.CharField(max_length=30)  # aagh, actually creator nickname
    num_players = models.IntegerField(default=1)
    num_starting_dice = models.IntegerField(default=5)
    max_pips = models.IntegerField(default=6)
    players_turn_order = models.CommaSeparatedIntegerField(max_length=100)
    players_untaken_turn = models.CommaSeparatedIntegerField(max_length=100)
    game_round_ctr = models.IntegerField(default=0)
    round_status_ctr = models.IntegerField(default=0)
    last_bid_player_id = models.IntegerField(default=0)
    last_bid_dice = models.IntegerField(default=0)
    last_bid_pips = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    indt = models.DateTimeField(auto_now_add=True)
    updt = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    open_games = OpenGameManager()

    def __unicode__(self):
        return u'%i %s %i %s %s' % (self.id, self.name, 
                self.num_players, self.get_joined_player_count(), self.indt)

    #TODO: need some optimistic locking here, before EVERY save.
    def add_player(self, nickname, is_human):
        nickname = re.sub(r'\W', '', nickname)
        pnames = [p.nickname for p in self.player_set.all()] 
        if nickname in pnames:
            raise Game.InvalidPlayer('Nickname is already taken for this game.')
        if self.get_joined_player_count() >= self.num_players:
            raise Game.InvalidPlayer('Game is full, no new players permitted.')
        p = self.player_set.create(game=self, 
                nickname=nickname,
                is_human=is_human,
                dice=self._get_random_dice(self.num_starting_dice))

        pids = self.players_turn_order.split(',')
        if pids[0]:
            pids.append(str(p.id))
        # NO players yet? pids == [''], don't join, create fresh list instead.
        else:
            pids = list(str(p.id))
        self.players_turn_order = ','.join(pids)
        
        # either start game, or inc round to tell about newly joined player. 
        if self.get_joined_player_count() == self.num_players:
            self._prep_new_game_for_play()
        else:
            self.round_status_ctr = self.round_status_ctr + 1
        self.save()

        return p

    #some invalid responses, just return None, trust js refresh to recover.
    #javascript SHOULD ensure new bid is always higher, but doublecheck. 
    def apply_bid(self, player_id, dice_count, pips):
        if not self._is_requesters_turn(player_id):
            return
        if (dice_count < self.last_bid_dice):
            return
        if (dice_count == self.last_bid_dice) and (pips <= self.last_bid_pips):
            return
        p = Player.objects.get(pk=player_id)
        msg = (p.nickname + ' bids ' + 
                get_text_from_dice_and_pips(dice_count, pips) + '.')
        self.roundmessage_set.create(game=self,
                game_round_ctr=self.game_round_ctr,
                message_type='std',
                message=msg)
        self.players_untaken_turn= self._get_next_players_untaken_turn()
        self.last_bid_player_id = player_id
        self.last_bid_dice = dice_count 
        self.last_bid_pips = pips 
        self.round_status_ctr = self.round_status_ctr + 1
        self.save()
        return
        
    def apply_challenge(self, player_id):
        if not self._is_requesters_turn(player_id):
            return  #no error, trust refresh to recover properly.
        #figure out who won, then start new round, THEN add msgs.
        ps = self.player_set.all()
        player_dice = dict([(p.nickname, p.get_dice_count()) for p in ps])
        match_dice = 0
        chger = [p for p in ps if p.id == player_id][0]
        chgee = [p for p in ps if p.id == self.last_bid_player_id][0]
        msgs = []
        msgs.append(chger.nickname + ' says NO WAY to ' 
                + get_text_from_dice_and_pips(self.last_bid_dice, self.last_bid_pips) 
                + '.')
        msgs.append('')
        for p in ps:
            match_dice = match_dice + len([d for d in p.dice.split(',') 
                if int(d) == self.last_bid_pips])
            msgs.append(p.nickname + ' has ' + p.dice.replace(',', ' - '))
        msgs.append('')
        msgs.append('. . . for a total of ' 
                + get_text_from_dice_and_pips(match_dice, self.last_bid_pips) 
                + '.')
        if match_dice >= self.last_bid_dice:
            self._set_and_save_challenge_winner_and_loser(chgee, chger, msgs)
        else:
            self._set_and_save_challenge_winner_and_loser(chger, chgee, msgs)

        self._init_and_save_post_challege_new_round(msgs)

    def _set_and_save_challenge_winner_and_loser(self, winner, loser, msgs):
        msgs.append(winner.nickname + ' wins the challenge. ' 
                + loser.nickname + ' loses a die.')
        loser.dice = ','.join(loser.dice.split(',')[1:])
        if not loser.dice:
            self.players_turn_order = ','.join(
                    [p for p in self.players_turn_order.split(',')
                    if p != str(loser.id)])
        self._apply_turn_order_cycling(winner.id)
        if len(self.players_turn_order.split(',')) == 1:
            msgs.append(winner.nickname + ' wins the game.')
            self.is_active = False
        winner.save()
        loser.save()

    def _init_and_save_post_challege_new_round(self, msgs):
        self.players_untaken_turn = self.players_turn_order 
        self.game_round_ctr = self.game_round_ctr + 1
        self.round_status_ctr = 1
        self.last_bid_dice = 0
        self.last_bid_pips = 0
        #ok to include "out" players here.
        for p in self.player_set.all():
            p.dice = self._get_random_dice(p.get_dice_count())
            p.save()
        #TODO: pretty sure I'm doing a pile of db calls here, rewrite
        for m in msgs:
            self.roundmessage_set.create(game=self,
                    game_round_ctr=self.game_round_ctr,
                    message_type='std',
                    message=m)
        self.save()

    #doesn't save, relies on caller to save.
    def _prep_new_game_for_play(self):
        # pids should never be [''] at this point. if I'm wrong, ugly mess.
        pids = self.players_turn_order.split(',')
        random.shuffle(pids)
        self.players_turn_order = ','.join(pids)
        self.players_untaken_turn = self.players_turn_order 
        self.game_round_ctr = self.game_round_ctr + 1
        self.round_status_ctr = 1
    
    def get_joined_player_count(self):
        ps = self.players_turn_order.split(',')
        # if no players, will get [''] not [], so check p[0]
        if ps[0]:
            return len(ps)
        else:
            return 0

    def get_game_listing_text(self):
        td = datetime.now() - self.indt
        if td.seconds < 11:
            age = 'just started'
        elif td.seconds < 120:
            age = '' + str(td.seconds) + ' seconds old'
        else:
            age = '' + str(td.seconds // 60) + ' minutes old'

        return (self.name + ', ' + str(self.num_players) + ' player game, '
                + str(self.get_joined_player_count()) + ' joined, ' + age)

    # return dict to avoid requery. kinda complex, better way?
    def get_game_summary_dict(self, request_player_id):
        ps = self.player_set.all()
        others_die_count = dict([(p.nickname, p.get_dice_count()) for p in ps
            if p.id != request_player_id])
        #not entirely sure we need list of ints, char might be ok?
        request_player_dice = [[int(d) for d in p.dice.split(',')]
                for p in ps 
                if p.id == request_player_id][0]
        return {'othersDieCount': others_die_count, 
                'yourDice': request_player_dice}

    def get_round_summary_dict(self, request_player_id):
        messages = [[rm.message_type, rm.message] 
                for rm in self.roundmessage_set.filter(
            game_round_ctr = self.game_round_ctr)] 

        return {'roundMessages': messages,
                'roundStatusCounter': self.round_status_ctr,
                'lastBidDice': self.last_bid_dice,
                'lastBidPips': self.last_bid_pips,
                'isYourTurn': self._is_requesters_turn(request_player_id),
                'isGameActive': self.is_active }

    def get_unjoined_player_count(self):
        return self.num_players - self.get_joined_player_count()

    def get_joined_player_names(self):
        return [p.nickname for p in self.player_set.all()] 

    def _get_random_dice(self, num_dice):
        dice = []
        for i in xrange(num_dice):
            dice.append(str(random.randint(1, self.max_pips)))
        return ','.join(dice)

    def _get_next_players_untaken_turn(self):
        put = self.players_untaken_turn.split(',')
        nput = put[1:]
        if len(nput) > 0:
            return ','.join(nput)
        else:
            return self.players_turn_order

    # modifies game but DOES NOT SAVE
    def _apply_turn_order_cycling(self, winner_id):
        pto = self.players_turn_order.split(',') 
        i = 0  # TODO: take out this chickenshit after testing
        while int(pto[0]) != winner_id:
            pto.append(pto.pop(0))
            i = i + 1
            if i > 100: 
                raise IndexError('cycle turn order broke')
        self.players_turn_order = ','.join(pto)

    def _is_requesters_turn(self, request_player_id):
        next_player_id = [int(p) for p 
                in self.players_untaken_turn.split(',')][0]
        return (next_player_id == request_player_id)

    class InvalidPlayer(Exception):
        def __init__(self, value):
            self.value = value
        def __unicode__(self):
            return self.value

#assuming that players only exist in context of game
# i'm not sure I want that assumption.
# on the other hand, might just keep nick around as a cookie
# and default new player name using cookie, i think that 
# is what dominion used to do.
class Player(models.Model):
    game = models.ForeignKey(Game)
    is_human = models.BooleanField(default=True)
    nickname = models.CharField(max_length=30)
    dice = models.CommaSeparatedIntegerField(max_length=100)  
    #might associate with user profile later

    def get_dice_count(self):
        return len(self.dice.split(','))

    def __unicode__(self):
        return u'%i %i %s %i %s' % (self.id, self.game.id, self.nickname,
                self.is_human, self.dice)

class RoundMessage(models.Model):
    game = models.ForeignKey(Game)
    game_round_ctr = models.IntegerField()
    message_type = models.CharField(max_length=20)
    message = models.CharField(max_length=60)


