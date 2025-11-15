# import aiohttp
# import config


# async def get_interpretation_from_n8n(cards, spread_type, username, question=None):
#     async with aiohttp.ClientSession() as session:
#         payload = {"cards": cards, "spread": spread_type, "user": username}
#         if question:
#             payload["question"] = question
#         async with session.post(config.N8N_WEBHOOK_URL, json=payload) as resp:
#             try:
#                 data = await resp.json()
#                 if isinstance(data, list):
#                     data = data[0]
#                 return data.get("interpretation", "⚠️ Не вдалося отримати тлумачення.")
#             except Exception as e:
#                 print(f"[ERROR] N8N response error: {e}")
#                 return "⚠️ Помилка при зверненні до n8n."


# # modules/n8n_api.py

# import aiohttp
# from typing import List, Dict, Any

# import config  # тут зручно зберігати URL





# # async def get_tarot_dialog_interpretation(
# #     user_name: str,
# #     question: str,
# #     cards: List[Dict[str, Any]],
# # ) -> str:
# #     """
# #     Викликає n8n webhook, який звертається до GPT і повертає вже готовий текст тлумачення.
# #     cards: список словників:
# #         {
# #           "code": "The Fool",
# #           "ua_name": "🤹‍♂️ Блазень",
# #           "upright": True/False
# #         }
# #     """
# #     url = config.N8N_WEBHOOK_URL

# #     payload = {
# #         "user": user_name,
# #         "question": question,
# #         "cards": cards,
# #         "spread": "dialog",
# #     }

# #     async with aiohttp.ClientSession() as session:
# #         async with session.post(url, json=payload, timeout=90) as resp:
# #             resp.raise_for_status()
# #             data = await resp.json()

# #     # Очікуємо відповідь формату:
# #     # { "interpretation": "тут текст" }
# #     text = data.get("interpretation")
# #     if not text:
# #         # На випадок, якщо ти просто повертаєш raw text
# #         if isinstance(data, str):
# #             return data
# #         return "⚠️ Не вдалося отримати тлумачення від таролога."
# #     return text
