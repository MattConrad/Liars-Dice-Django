# maybe __init.py__ is not the best way to handle this.
# could make static vars/methods on Game instead, probably. 

pip_names_single = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five',
            6: 'six', 7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten' }

def get_text_from_dice_and_pips(dice, pips):
    if dice == 1:
        return '1 ' + pip_names_single[pips]
    else:
        if pips == 6:
            return str(dice) + ' sixes'
        else:
            return str(dice) + ' ' + pip_names_single[pips] + 's'

