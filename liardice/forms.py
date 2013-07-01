from django import forms 

NUMBER_PLAYERS_CHOICES = (
    ('2', '2'),
    ('3', '3'),
    ('4', '4'),
    ('5', '5'),
    ('6', '6'),
    ('7', '7'),
    ('8', '8'),
)
 
class NewGameForm(forms.Form):
    #num_players = forms.IntegerField()
    number_of_players = forms.ChoiceField(choices=NUMBER_PLAYERS_CHOICES, required=True)

