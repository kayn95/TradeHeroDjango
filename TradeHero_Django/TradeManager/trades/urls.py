# TradeManager/trades/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Home & erreurs
    path("", views.home, name="home"),
    path("non_authorise/", views.non_authorise, name="non_authorise"),

    # Auth
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    path("register/", views.register, name="register"),

    # Trades
    path("trades/", views.trade_list, name="trade_list"),
    path("trades/new/", views.trade_new, name="trade_new"),
    path("trades/<int:pk>/", views.trade_detail, name="trade_detail"),
    path("trades/<int:pk>/edit/", views.trade_edit, name="trade_edit"),
    path("trades/<int:pk>/delete/", views.trade_delete, name="trade_delete"),
    path("trades/<int:pk>/note/", views.update_trade_note, name="update_trade_note"),
    path("trades/<int:trade_id>/add_screenshot/", views.add_trade_screenshot, name="add_trade_screenshot"),
    path("trades/<int:trade_id>/update_strategy/", views.update_trade_strategy, name="update_trade_strategy"),

    # Stratégies
    path("strategies/", views.strategy_list, name="strategy_list"),
    path("strategies/new/", views.strategy_new, name="strategy_new"),
    path("strategies/<int:pk>/", views.strategy_detail, name="strategy_detail"),
    path("strategies/<int:pk>/edit/", views.strategy_edit, name="strategy_edit"),
    path("strategies/<int:pk>/delete/", views.strategy_delete, name="strategy_delete"),

    # Coach / élève
    path("coach/students/", views.coach_students_list, name="coach_students_list"),
    path("coach/students/<int:student_id>/trades/", views.coach_student_trades, name="coach_student_trades"),
    path("coach/choose/", views.choose_coach, name="choose_coach"),
    path("coach/pending_requests/", views.coach_pending_requests, name="coach_pending_requests"),
    path("coach/respond_request/<int:req_id>/", views.coach_respond_request, name="coach_respond_request"),
    path("coach/add_trade_comment/", views.add_trade_comment, name="add_trade_comment"),

    # Import CSV
    path("import_csv/", views.import_csv, name="import_csv"),

    # Stats
    path("stats/", views.stats_view, name="stats"),
]
