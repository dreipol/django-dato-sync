# django-dato-sync

django-dato-sync enables you to easily sync Dato records into your django database. Features include:

- Delta sync
- Automatic sync via Dato webhooks
- Localization support with [django-modeltranslation](https://github.com/deschler/django-modeltranslation)
- Configuration of which fields to sync
- Collecting information of multiple Dato records into a single django object

## Installation

1. Install the pip package:
```shell
pipenv install django-dato-sync
```
2. Add to your installed apps:
```py
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    ...
    "dato_sync",
]
```
3. Setup at least the following settings:
```py
DATOCMS_API_TOKEN: str = ...
DATOCMS_API_URL: str = ...
DATOCMS_ENVIRONMENT: str = ...
```

### Optional: Setup for automatic syncing via Webhooks
1. Add the following to your `urls.py`:
```py
urlpatterns = [
    ...
    path("", include("dato_sync.urls"))
]
```
2. Use `python manage.py gen_auth_header` to generate the auth setup. Add `DATO_SYNC_WEBHOOK_EXPECTED_AUTH: str` to your `settings.py` and set up the username and password in Dato.
3. In Dato navigate to Project Setting > Automations > Webhooks and click "Add a new webhook"
4. Configure the webhook to trigger on "Publish", "Unpublish", and "Delete" for any records you want to sync to django
5. Specify the URL as `https://<your-django-server-address>/dato-sync/sync/`
6. Configure the "HTTP basic auth" to match the header you configured in step 2

## Usage
1. Create your local django model but make sure it inherits from `DatoModel` (it will automatically have fields for the `dato_identifier` (pk), `created` and `modified` dates (corresponding to changes made in Dato) and a `deleted` field indicating a soft delete)
```py
class MyModel(DatoModel):
    name = models.TextField()
    order = models.IntegerField()
    note = models.TextField()
```
2. Create a `dato_sync.py` file in your app:
```py
@fetch_from_dato(MyModel)
class MyModelSyncOptions(SyncOptions):
    dato_model_path = "my_model"
    field_mappings = [
        "order" |position_in_parent,
        "name",
    ]
```
3. To sync either have Dato call the webhook (see above) or use
```shell
python manage.py sync_dato [--force-full-sync]
```

### Configuration Options
#### dato_model_path
Configure the dato entity your model corresponds to. If you are mapping a Dato model directly this is just its model id. If you're using blocks you can chain them like `my_model.parent_block.child_block`.

⚠️ Make sure that all blocks have the same schema. Fields that can contain different types of blocks are currently not supported.

#### field_mappings
Here you specify which fields should be synced with dato. If you leave out fields (like the `notes` field in the example above they can be edited locally).

In the simplest case when the name of your field in django corresponds to the api name in Dato, you can simply add it to the field mappings as we did with `"name"`. For more complicated scenarios you can write:
```py
field_mappings = [
    "name" |from_dato_path("my_model.title", localized=True, absolute=True),
]
```
This allows you to

- specify a different name / path to take the value from
- `localized` allows you to fetch localizations from Dato and store them either
  - using [django-modeltranslation](https://github.com/deschler/django-modeltranslation)
  - by manually defining fields with the `_<language_code>` suffix (e.g. `foo_de`, `foo_fr`) 
- `absolute` allows you to access properties of the parent entities by specifying the field to take the value from starting from the top of the Dato query rather than the path specified in `dato_model_path`

Additonally the following are also available:
- `|position_in_parent` to obtain the position of the item in its parent
- `|flattened_position` to obtain a global order by flattening the list across all paths

#### ArrayFields
Postgres ArrayFields are supported ⚠️ so long as there is no nesting on either the Dato or django side ⚠️. Simply specify the path like:
```py
"tags" |from_dato_path("tags.name")
```
and django-dato-sync will automatically collect the names of all tags into an array.

## Tips and Tricks
- Foreign key relationships are not supported directly, but you can use django's `..._id` field to set the id of another Dato object
  - ⚠️ Make sure to sync the related objects first to avoid foreign key constraint violations. Sync operations are executed in the same order they appear in the `dato_sync.py` file.
  - For one-to-many relationships use absolute paths to access the parent's id
- You can create multiple sync jobs for the same django model to collect all instances of a block across multiple models into one django table