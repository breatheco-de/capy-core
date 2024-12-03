# Query params

Capy Serializers supports automatic filtering from query params out of the box, this fields are limited from `filters` attribute and inherit the filters from its children.

## Operations

### Greater than

```http
GET /api/v1/users?age>18
```

### Less than

```http
GET /api/v1/users?age<18
```

### Greater than or equal to

```http
GET /api/v1/users?age>=18
```

### Less than or equal to

```http
GET /api/v1/users?age<=18
```

### Equal to

```http
GET /api/v1/users?age=18
```

### Not equal to

```http
GET /api/v1/users?age!=18
```

### In

```http
GET /api/v1/users?age=18,20,22
```

### Django Lookup

The supported filters are `exact`, `iexact`, `contains`, `icontains`, `gt`, `gte`, `lt`, `lte`, `in`, `startswith`, `istartswith`, `endswith`, `iendswith`, `range`, `year`, `month`, `day`, `hour`, `minute`, `second`, `isnull`, `search`.

```http
GET /api/v1/users?age[in]=18,20,22
```

### Not

This operator is able to negate all the supported operations previously mentioned.

```http
GET /api/v1/users?age!=18
```
