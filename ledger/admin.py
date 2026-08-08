from django.contrib import admin

from .models import Expense, ExpenseShare, Group


class ExpenseShareInline(admin.TabularInline):
    model = ExpenseShare
    extra = 0


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "member_count", "created_at")
    search_fields = ("name",)
    filter_horizontal = ("members",)

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("description", "group", "payer", "amount", "split_type", "created_at")
    list_filter = ("split_type", "group", "created_at")
    search_fields = ("description", "payer__username")
    date_hierarchy = "created_at"
    inlines = [ExpenseShareInline]


@admin.register(ExpenseShare)
class ExpenseShareAdmin(admin.ModelAdmin):
    list_display = ("expense", "user", "amount_owed")
    list_filter = ("expense__group",)
    search_fields = ("user__username", "expense__description")
