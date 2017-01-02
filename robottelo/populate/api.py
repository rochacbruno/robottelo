"""Implements API populator"""
from robottelo.populate.base import BasePopulator
from nailgun import entities
from nailgun.entity_mixins import EntitySearchMixin
from requests.exceptions import HTTPError


class APIPopulator(BasePopulator):
    """Populates system using API/Nailgun"""

    def populate(self, entity_data, action_data, search_query, action):
        """Populates the System using Nailgun
        threats and logs Exceptions
        takes care of adding valid entity to the registry
        """
        model = getattr(entities, action_data['model'])
        silent_errors = action_data.get('silent_errors', False)

        if not issubclass(model, EntitySearchMixin):
            if silent_errors:
                return
            raise TypeError("{0} not searchable".format(model))

        try:
            # self.create|update|delete
            result = getattr(self, action)(
                entity_data, action_data, search_query, model
            )
        except HTTPError as e:
            self.logger.error(str(e))
            if hasattr(e, 'response'):
                self.logger.info(e.response.content)
        except Exception:
            if silent_errors:
                return
            raise
        else:
            self.add_to_registry(action_data, result)

    def create(self, entity_data, action_data, search_query, model):
        """Creates new entity if does not exists"""
        # 1) check if entity already exists
        search_result = model().search(**search_query)
        if search_result:
            if len(search_result) > 1:
                self.logger.info(search_result)
                raise RuntimeError(
                    "More than 1 item returned "
                    "search_data query is not unique"
                )
            # existent entity should be unique, so it is the first
            # item in search_result
            result = search_result[0]
            self.total_existing += 1
        else:
            result = model(**entity_data).create()
            self.total_created += 1
        return result

    def update(self, entity_data, action_data, search_query, model):
        """Updates an entity"""

        search_data = action_data.get('search_data')
        entity_id = action_data.get('id')

        if not entity_id and not search_data:
            raise RuntimeError("update: missing id or search_query")

        if not entity_id:
            search_result = model().search(**search_query)
            if not search_result:
                raise RuntimeError("update: Cannot find entity")

            entity_id = search_result[0].id

        entity = model(id=entity_id, **entity_data)
        entity.update(entity_data.keys())
        return entity

    def delete(self, entity_data, action_data, search_query, model):
        """Deletes an entity"""

        search_data = action_data.get('search_data')
        entity_id = action_data.get('id')

        if not entity_id and not search_data:
            raise RuntimeError("delete: missing id or search_query")

        if not entity_id:
            search_result = model().search(**search_query)
            if not search_result:
                raise RuntimeError("delete: Cannot find entity")

            entity_id = search_result[0].id

        model(id=entity_id).delete()

    def validate(self, entity_data, action_data, search_query, action):
        """Based on predefined `search_data` or using
        raw_entity['search_data'] searches the system
        and validates the existence of all entities"""
        if action != 'create' or action_data.get('skip_validation'):
            # validate only create actions
            return

        model = getattr(entities, action_data['model'])

        if not issubclass(model, EntitySearchMixin):
            raise TypeError("{0} not searchable".format(model))

        try:
            # 1) check if entity exists
            search_result = model().search(**search_query)
            if search_result:
                if len(search_result) > 1:
                    self.logger.info(search_result)
                    raise RuntimeError(
                        "More than 1 item returned "
                        "search_data query is not unique"
                    )
                # existent entity should be unique, so it is the first
                # item in search_result
                result = search_result[0]
                self.total_existing += 1
            else:
                result = None
        except HTTPError as e:
            error_message = str(e)
            if hasattr(e, 'response'):
                error_message += e.response.content
            self.logger.error(error_message)
            self.validation_errors.append({
                'search_query': search_query,
                'message': error_message,
                'entity_data':  entity_data,
                'action_data': action_data
            })
        else:
            if result:
                self.add_to_registry(action_data, result)
            else:
                self.add_to_registry(action_data, None)
                self.validation_errors.append({
                    'search_query': search_query,
                    'message': 'entity does not exist in the system',
                    'entity_data':  entity_data,
                    'action_data': action_data
                })
