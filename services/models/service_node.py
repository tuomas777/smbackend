from django.db import models
from mptt.models import MPTTModel, TreeForeignKey
from mptt.managers import TreeManager
from services.utils import get_translated
from .keyword import Keyword
from .unit import Unit
from .hierarchy import CustomTreeManager
from .service import Service
from munigeo.models import AdministrativeDivisionType, AdministrativeDivision


class ServiceNode(MPTTModel):
    id = models.IntegerField(primary_key=True)
    ext_id = models.CharField(unique=True, max_length=200, blank=True, null=True)
    name = models.CharField(max_length=200, db_index=True)
    parent = TreeForeignKey('self', null=True, related_name='children')
    keywords = models.ManyToManyField(Keyword)

    service_reference = models.TextField(null=True)
    related_services = models.ManyToManyField(Service)

    last_modified_time = models.DateTimeField(db_index=True, help_text='Time of last modification')

    objects = CustomTreeManager()
    tree_objects = TreeManager()

    def __str__(self):
        return "%s (%s)" % (get_translated(self, 'name'), self.id)

    def get_unit_count(self):
        srv_list = set(ServiceNode.objects.all().by_ancestor(self).values_list('id', flat=True))
        srv_list.add(self.id)
        count = Unit.objects.filter(public=True, service_nodes__in=list(srv_list)).distinct().count()
        return count

    def period_enabled(self):
        """Iterates through related services to find out
        if the tree node has periods enabled via services"""
        return next((
            o.period_enabled
            for o in self.related_services.all()
            if o.period_enabled), False)

    class Meta:
        ordering = ['-pk']


class ServiceNodeUnitCount(models.Model):
    service_node = models.ForeignKey(ServiceNode, null=False, db_index=True, related_name='unit_counts')
    division_type = models.ForeignKey(AdministrativeDivisionType, null=False)
    division = models.ForeignKey(AdministrativeDivision, null=True, db_index=True)
    count = models.PositiveIntegerField(null=False)

    class Meta:
        unique_together = (('service_node', 'division'),)
