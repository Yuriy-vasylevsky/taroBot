# import random
# from cards_data import TAROT_CARDS

# def draw_card():
#     card_name = random.choice(list(TAROT_CARDS.keys()))
#     position = "reversed" if random.random() < 0.4 else "upright"
#     card = TAROT_CARDS[card_name]
#     meaning = card[f"meaning_{position}"]
#     ua_name = card["ua_name"]
#     image_path = card["image"]
#     orientation_ua = "⬆️" if position == "upright" else "⬇️"
#     return card_name, ua_name, position, orientation_ua, meaning, image_path
