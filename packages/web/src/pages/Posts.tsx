import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { createPost, deletePost, listPosts, updatePost, type Post } from '@/services/posts'
import { useAuth } from '@/contexts/AuthContext'

type FormState = {
  title: string
  content: string
  published: boolean
}

const initialForm: FormState = {
  title: '',
  content: '',
  published: false,
}

function Posts() {
  const { user, logout } = useAuth()
  const [posts, setPosts] = useState<Post[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(initialForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    void loadPosts()
  }, [])

  async function loadPosts() {
    try {
      setLoading(true)
      setError('')
      setPosts(await listPosts())
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '加载 Posts 失败')
    } finally {
      setLoading(false)
    }
  }

  function resetForm() {
    setEditingId(null)
    setForm(initialForm)
  }

  function startEdit(post: Post) {
    setEditingId(post.id)
    setForm({
      title: post.title,
      content: post.content ?? '',
      published: post.published,
    })
    setError('')
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()

    try {
      setSaving(true)
      setError('')

      if (editingId) {
        const updated = await updatePost(editingId, form)
        setPosts((current) => current.map((post) => (post.id === updated.id ? updated : post)))
      } else {
        const created = await createPost(form)
        setPosts((current) => [created, ...current])
      }

      resetForm()
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '保存 Post 失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id: string) {
    try {
      setError('')
      await deletePost(id)
      setPosts((current) => current.filter((post) => post.id !== id))
      if (editingId === id) {
        resetForm()
      }
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || '删除 Post 失败')
    }
  }

  return (
    <main className="detail-app">
      <section className="detail-shell">
        <nav className="nav-bar">
          <Link to="/" className="nav-link">首页</Link>
          <div className="nav-spacer" />
          <div className="user-bar">
            <span className="user-name">{user?.nickname || user?.id || '用户'}</span>
            <button className="btn btn-ghost btn-xs" onClick={logout}>退出</button>
          </div>
        </nav>

        <header className="hero compact-hero">
          <div>
            <p className="eyebrow">Posts CRUD</p>
            <h1>Posts 示例</h1>
            <p className="hero-copy">最小可运行的受保护 CRUD 页面，演示 Fastify + Prisma + React 协作。</p>
          </div>
        </header>

        {error ? <div className="state-card error-state">{error}</div> : null}

        <div className="posts-layout">
          <section className="card posts-form-card">
            <h2>{editingId ? '编辑 Post' : '新建 Post'}</h2>
            <form className="login-form" onSubmit={handleSubmit}>
              <label className="login-field">
                <span>标题</span>
                <input
                  type="text"
                  value={form.title}
                  onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                  placeholder="请输入标题"
                />
              </label>

              <label className="login-field">
                <span>内容</span>
                <textarea
                  value={form.content}
                  onChange={(event) => setForm((current) => ({ ...current, content: event.target.value }))}
                  placeholder="请输入内容"
                  rows={6}
                />
              </label>

              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={form.published}
                  onChange={(event) => setForm((current) => ({ ...current, published: event.target.checked }))}
                />
                <span>Published</span>
              </label>

              <div className="posts-form-actions">
                <button className="btn btn-accent" type="submit" disabled={saving}>
                  {saving ? '保存中...' : editingId ? '更新' : '创建'}
                </button>
                {editingId ? (
                  <button className="btn btn-ghost" type="button" onClick={resetForm}>
                    取消
                  </button>
                ) : null}
              </div>
            </form>
          </section>

          <section className="card posts-list-card">
            <div className="section-head">
              <h2>我的 Posts</h2>
              <button className="btn btn-ghost btn-xs" type="button" onClick={() => void loadPosts()}>
                刷新
              </button>
            </div>

            {loading ? <div className="state-card">加载中...</div> : null}
            {!loading && posts.length === 0 ? <div className="state-card">还没有 Post，先创建一条。</div> : null}

            <div className="posts-list">
              {posts.map((post) => (
                <article key={post.id} className="post-item">
                  <div className="post-item-head">
                    <div>
                      <h3>{post.title}</h3>
                      <p className="muted-copy">{new Date(post.updatedAt).toLocaleString()}</p>
                    </div>
                    <span className={`soft-pill ${post.published ? 'pill-published' : 'pill-draft'}`}>
                      {post.published ? 'Published' : 'Draft'}
                    </span>
                  </div>
                  <p className="post-item-content">{post.content || '暂无内容'}</p>
                  <div className="posts-item-actions">
                    <button className="btn btn-ghost btn-xs" type="button" onClick={() => startEdit(post)}>
                      编辑
                    </button>
                    <button className="btn btn-ghost btn-xs" type="button" onClick={() => void handleDelete(post.id)}>
                      删除
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  )
}

export default Posts
