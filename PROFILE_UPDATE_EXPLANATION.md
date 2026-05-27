# Profile Update Endpoint & Serializer - Complete Breakdown

## 📍 **The Endpoint: `/api/users/me/` or `/api/user/`**

The `ProfileView` class handles 3 HTTP methods:

### 1. **GET** - Retrieve Profile
```python
GET /api/users/me/
Headers: Authorization: Bearer <token>
```
**What it does:**
- Gets the logged-in user (`request.user`)
- Serializes their data into JSON
- Returns: `{id, username, email, first_name, last_name, full_name, initials, phone, avatar, avatar_url}`

---

### 2. **PUT** - Full Update (All Fields Required)
```python
PUT /api/users/me/
Headers: Authorization: Bearer <token>
Content-Type: application/json
Body: {username, first_name, last_name, phone, avatar}
```
**What it does:**
- Requires ALL updatable fields to be sent
- Replaces entire profile with new data
- Use when you want to update everything at once

**Example:**
```json
{
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890"
}
```

---

### 3. **PATCH** - Partial Update (Only Send What You Want to Change)
```python
PATCH /api/users/me/
Headers: Authorization: Bearer <token>
Content-Type: application/json (or multipart/form-data for images)
Body: {first_name}  // Only send fields you want to update
```
**What it does:**
- Only updates the fields you send
- Other fields remain unchanged
- **This is what you'll use most often!**

**Example - Update only first name:**
```json
{
  "first_name": "Jane"
}
```

**Example - Update username and phone:**
```json
{
  "username": "janedoe",
  "phone": "+9876543210"
}
```

**Example - Upload avatar (multipart/form-data):**
```
POST /api/users/me/
Content-Type: multipart/form-data
avatar: <image file>
```

---

## 🔍 **The Serializer: `UserProfileSerializer`**

The serializer does 3 main jobs:

### **Job 1: Define What Fields Can Be Read/Written**

```python
fields = (
    'id', 'username', 'email', 'first_name', 'last_name', 
    'full_name', 'initials', 'phone', 'avatar', 'avatar_url'
)

read_only_fields = ('id', 'email', 'full_name', 'initials', 'avatar_url')
```

**Read-only fields** (can't be changed):
- `id` - Auto-generated, never changes
- `email` - Can't change email via this endpoint
- `full_name` - Auto-calculated from first_name + last_name
- `initials` - Auto-calculated from first_name + last_name
- `avatar_url` - Auto-generated URL (S3 or local)

**Writable fields** (can be updated):
- `username` - Can change
- `first_name` - Can change
- `last_name` - Can change
- `phone` - Can change
- `avatar` - Can upload/change image

---

### **Job 2: Validate Data Before Saving**

Before saving, the serializer checks each field:

#### **Username Validation:**
```python
def validate_username(self, value):
    # 1. Can't be empty
    if not value:
        raise ValidationError('Username cannot be empty')
    
    # 2. Must be at least 3 characters
    if len(value) < 3:
        raise ValidationError('Username must be at least 3 characters long')
    
    # 3. Only letters, numbers, underscore, hyphen allowed
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        raise ValidationError('Username can only contain letters, numbers, underscores, and hyphens')
    
    # 4. Can't be taken by another user
    if User.objects.filter(username=value).exists():
        raise ValidationError('This username is already taken')
    
    return value
```

**Examples:**
- ✅ `"johndoe"` → Valid
- ✅ `"john_doe"` → Valid
- ✅ `"john123"` → Valid
- ❌ `"jo"` → Too short (needs 3+ chars)
- ❌ `"john doe"` → Invalid (no spaces)
- ❌ `"john@doe"` → Invalid (no @ symbol)
- ❌ `"existinguser"` → Invalid if already taken

#### **First/Last Name Validation:**
```python
def validate_first_name(self, value):
    # Can't be just whitespace
    if value and len(value.strip()) < 1:
        raise ValidationError('First name cannot be empty')
    # Remove extra spaces
    return value.strip() if value else value
```

#### **Phone Validation:**
```python
def validate_phone(self, value):
    if value:
        # Remove formatting, keep only digits
        cleaned = ''.join(filter(str.isdigit, value))
        # Must have at least 10 digits
        if len(cleaned) < 10:
            raise ValidationError('Phone number must contain at least 10 digits')
    return value
```

**Examples:**
- ✅ `"+1234567890"` → Valid (10+ digits)
- ✅ `"(123) 456-7890"` → Valid (10+ digits after cleaning)
- ✅ `"1234567890"` → Valid
- ❌ `"123"` → Invalid (less than 10 digits)

---

### **Job 3: Save Data to Database**

```python
def update(self, instance, validated_data):
    # instance = the current user object
    # validated_data = the cleaned, validated data from request
    
    # Step 1: Remember old avatar (to delete it later)
    old_avatar = instance.avatar
    
    # Step 2: Update text fields
    for field in ['username', 'first_name', 'last_name', 'phone']:
        if field in validated_data:
            setattr(instance, field, validated_data[field])
            # This is like: instance.username = validated_data['username']
    
    # Step 3: Handle avatar (special case)
    if 'avatar' in validated_data:
        avatar = validated_data.get('avatar')
        # If uploading new avatar and old one exists, delete old one
        if avatar and old_avatar and old_avatar != avatar:
            old_avatar.delete(save=False)  # Delete from S3/local storage
        instance.avatar = avatar
    elif validated_data.get('avatar') is None:
        # User wants to remove avatar
        if old_avatar:
            old_avatar.delete(save=False)
        instance.avatar = None
    
    # Step 4: Save to database
    instance.save()
    return instance
```

**What happens:**
1. Updates username, first_name, last_name, phone if provided
2. If new avatar uploaded → deletes old avatar, saves new one
3. If avatar set to null → deletes old avatar, sets to None
4. Saves everything to database
5. Returns updated user object

---

## 🔄 **Complete Flow Example**

### **Scenario: User wants to update their first name and phone**

**Step 1: Frontend sends request**
```http
PATCH /api/users/me/
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: application/json

{
  "first_name": "Jane",
  "phone": "+1234567890"
}
```

**Step 2: ProfileView receives request**
```python
# request.user = <User: johndoe>
# request.data = {'first_name': 'Jane', 'phone': '+1234567890'}
```

**Step 3: Serializer validates**
```python
# validate_first_name('Jane') → ✅ Valid, returns 'Jane'
# validate_phone('+1234567890') → ✅ Valid (10+ digits), returns '+1234567890'
```

**Step 4: Serializer updates**
```python
# instance.first_name = 'Jane'
# instance.phone = '+1234567890'
# instance.save()  # Saves to database
```

**Step 5: Response sent back**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "first_name": "Jane",  // ✅ Updated
  "last_name": "Doe",
  "full_name": "Jane Doe",  // ✅ Auto-updated
  "initials": "JD",  // ✅ Auto-updated
  "phone": "+1234567890",  // ✅ Updated
  "avatar": null,
  "avatar_url": null
}
```

---

## 📝 **Common Use Cases**

### **1. Update Username Only**
```json
PATCH /api/users/me/
{
  "username": "newusername"
}
```

### **2. Update Name**
```json
PATCH /api/users/me/
{
  "first_name": "Jane",
  "last_name": "Smith"
}
```

### **3. Update Phone**
```json
PATCH /api/users/me/
{
  "phone": "+1234567890"
}
```

### **4. Upload Avatar (multipart/form-data)**
```http
PATCH /api/users/me/
Content-Type: multipart/form-data

avatar: <binary image data>
```

### **5. Remove Avatar**
```json
PATCH /api/users/me/
{
  "avatar": null
}
```

### **6. Update Everything**
```json
PUT /api/users/me/
{
  "username": "janedoe",
  "first_name": "Jane",
  "last_name": "Doe",
  "phone": "+1234567890"
}
```

---

## ⚠️ **Error Handling**

If validation fails, you get a 400 Bad Request:

```json
{
  "username": ["Username must be at least 3 characters long"]
}
```

Or:
```json
{
  "phone": ["Phone number must contain at least 10 digits"]
}
```

---

## 🎯 **Key Takeaways**

1. **Use PATCH** for partial updates (most common)
2. **Use PUT** for full updates (less common)
3. **Validation happens automatically** - you don't need to check in frontend
4. **Old avatars are deleted automatically** when you upload new ones
5. **Read-only fields** (`full_name`, `initials`) are calculated automatically
6. **All updates require authentication** (Bearer token)

---

## 🔧 **Frontend Integration Example**

```dart
// Flutter/Dart example
Future<void> updateProfile({
  String? firstName,
  String? lastName,
  String? username,
  String? phone,
}) async {
  final prefs = await SharedPreferences.getInstance();
  final token = prefs.getString('access_token');
  
  final response = await http.patch(
    Uri.parse('${apiBaseUrl}users/me/'),
    headers: {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    },
    body: json.encode({
      if (firstName != null) 'first_name': firstName,
      if (lastName != null) 'last_name': lastName,
      if (username != null) 'username': username,
      if (phone != null) 'phone': phone,
    }),
  );
  
  if (response.statusCode == 200) {
    final data = json.decode(response.body);
    return UserModel.fromJson(data);
  } else {
    throw Exception('Update failed: ${response.body}');
  }
}
```

---

That's it! The serializer handles all validation and saving automatically. You just send the data you want to update, and it does the rest! 🚀

