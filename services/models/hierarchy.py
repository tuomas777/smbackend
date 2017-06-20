from django.db.models import QuerySet, Q
from mptt.models import TreeManager


class CustomTreeManager(TreeManager):
    def get_queryset(self):
        return TreeQuerySet(self.model, using=self._db)

    def determine_max_level(self):
        if hasattr(self, '_max_level'):
            return self._max_level
        qs = self.all().order_by('-level')
        if qs.count():
            self._max_level = qs[0].level
        else:
            # Harrison-Stetson method
            self._max_level = 10
        return self._max_level


class TreeQuerySet(QuerySet):
    def by_ancestor(self, ancestor):
        manager = self.model.objects
        max_level = manager.determine_max_level()
        qs = Q()
        # Construct an OR'd queryset for each level of parenthood.
        for i in range(max_level):
            key = '__'.join(['parent'] * (i + 1))
            qs |= Q(**{key: ancestor})
        # TODO Turku POC
        # return self.filter(qs)
        return self.filter(qs) if qs else self.none()
