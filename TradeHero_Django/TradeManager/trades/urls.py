# trades/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # Trades URLs
    path('trades/', views.trade_list, name='trade_list'),
    path('trade/<int:pk>/', views.trade_detail, name='trade_detail'),
    path('trade/new/', views.trade_new, name='trade_new'),
    path('trade/<int:pk>/edit/', views.trade_edit, name='trade_edit'),
    path('trade/<int:pk>/delete/', views.trade_delete, name='trade_delete'),
    path('trades/<int:pk>/update-note/', views.update_trade_note, name='update_trade_note'),
    # Strategies URLs
    path('strategies/', views.strategy_list, name='strategy_list'),
    path('strategy/<int:pk>/', views.strategy_detail, name='strategy_detail'),
    path('strategy/new/', views.strategy_new, name='strategy_new'),
    path('strategy/<int:pk>/edit/', views.strategy_edit, name='strategy_edit'),
    path('strategy/<int:pk>/delete/', views.strategy_delete, name='strategy_delete'),
    path('stats/', views.stats_view, name='stats_view'),
    # Auth URLs
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('import-csv/', views.import_csv, name='import_csv'),
    path('trades/<int:trade_id>/add_screenshot/', views.add_trade_screenshot, name='add_trade_screenshot'),
    path('trades/<int:trade_id>/update_strategy/', views.update_trade_strategy, name='update_trade_strategy'),
    path('trades/add-comment/', views.add_trade_comment, name='add_trade_comment'),
    path('choose-coach/', views.choose_coach, name='choose_coach'),
    path('coach/pending-requests/', views.coach_pending_requests, name='coach_pending_requests'),
    path('coach/pending-requests/<int:req_id>/respond/', views.coach_respond_request, name='coach_respond_request'),
    path('coach/students/', views.coach_students_list, name='coach_students_list'),
    path('coach/students/<int:student_id>/trades/', views.coach_student_trades, name='coach_student_trades'),
]
