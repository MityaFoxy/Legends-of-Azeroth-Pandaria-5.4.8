#!/usr/bin/env python3
"""Run real pool shutdown and worker methods on Asio; SQL storage is a double."""
from pathlib import Path
import subprocess
import sys
import tempfile
root, compiler = Path(sys.argv[1]), sys.argv[2]

def block(text, signature):
    a=text.index(signature); b=text.index('{',a)+1; depth=1
    while depth:
        depth+=(text[b]=='{')-(text[b]=='}'); b+=1
    return text[a:b]

pool=(root/'src/server/database/Database/DatabaseWorkerPool.cpp').read_text()
conn=(root/'src/server/database/Database/MySQLConnection.cpp').read_text()
fixed='void DatabaseWorkerPool<T>::StopAsyncWorkers()' in pool
prefix=r"""
#include <utility>
#include <boost/asio.hpp>
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <future>
#include <latch>
#include <memory>
#include <thread>
#include <vector>
#include "IoContext.h"
#define TC_LOG_INFO(...) ((void)0)
std::atomic<bool> joining=false;
struct MySQLConnection {
 std::unique_ptr<std::thread> m_workerThread; std::thread::id m_workerThreadId;
 std::thread::id GetWorkerThreadId() const;
 void StartWorkerThread(Trinity::Asio::IoContext*);
 void StopWorkerThread();
 ~MySQLConnection(){StopWorkerThread();}
};
template<class T> struct DatabaseWorkerPool {
 enum {IDX_ASYNC,IDX_SYNCH,IDX_SIZE};
 struct AsyncWork;
 std::unique_ptr<Trinity::Asio::IoContext> _ioContext;
 std::unique_ptr<AsyncWork> _asyncWork;
 std::array<std::vector<std::unique_ptr<T>>,IDX_SIZE> _connections;
 const char* GetDatabaseName(){return "fixture";}
 void Close();
 void StopAsyncWorkers();
 T* GetAsyncConnectionForCurrentThread() const;
};
"""
if fixed:
    prefix+='template<class T>\n'+block(pool,'struct DatabaseWorkerPool<T>::AsyncWork')+';\n'
    prefix+=block(conn,'void MySQLConnection::StopWorkerThread()').replace('m_workerThread->join();','joining=true; m_workerThread->join();')+'\n'
    prefix+='template<class T>\n'+block(pool,'void DatabaseWorkerPool<T>::StopAsyncWorkers()')+'\n'
else:
    prefix+='template<class T> struct DatabaseWorkerPool<T>::AsyncWork {};\n'
    prefix+='void MySQLConnection::StopWorkerThread(){if(m_workerThread){joining=true;m_workerThread->join();m_workerThread.reset();}}\n'
prefix+=block(conn,'std::thread::id MySQLConnection::GetWorkerThreadId() const')+'\n'
prefix+='template<class T>\n'+block(pool,'T* DatabaseWorkerPool<T>::GetAsyncConnectionForCurrentThread() const')+'\n'
prefix+=block(conn,'void MySQLConnection::StartWorkerThread(')+'\n'
prefix+='template<class T>\n'+block(pool,'void DatabaseWorkerPool<T>::Close()')+'\n'
main=(root/'src/server/worldserver/Main.cpp').read_text()
prefix+=r"""
namespace shutdown_fixture {
struct Pool {
 bool drained=false,closed=false;
 void StopAsyncWorkers(){drained=true;}
 void Close(){assert(drained);closed=true;}
} CharacterDatabase,WorldDatabase,LoginDatabase,PlayerbotsDatabase;
bool cleared=false;
void ClearOnlineAccounts(){
 assert(CharacterDatabase.drained&&WorldDatabase.drained&&LoginDatabase.drained&&PlayerbotsDatabase.drained);
 assert(!CharacterDatabase.closed&&!LoginDatabase.closed);cleared=true;
}
namespace MySQL {void Library_End(){assert(cleared&&CharacterDatabase.closed&&WorldDatabase.closed&&LoginDatabase.closed&&PlayerbotsDatabase.closed);}}
#define PLAYERBOTS 1
"""
prefix+=block(main,'void StopDB()\n')+'\n}\n'
checks=r"""
int main(){
 shutdown_fixture::StopDB();
 {DatabaseWorkerPool<MySQLConnection> empty;empty.Close();}
 for(int n:{1,4}) {
  DatabaseWorkerPool<MySQLConnection> pool;
  pool._ioContext=std::make_unique<Trinity::Asio::IoContext>(n);
  INIT_WORK
  for(int i=0;i<n;++i)pool._connections[0].push_back(std::make_unique<MySQLConnection>());
  for(auto& c:pool._connections[0])c->StartWorkerThread(pool._ioContext.get());
  std::latch entered(n),release(1);std::atomic<int> rows=0;joining=false;
  for(int i=0;i<n;++i)boost::asio::post(pool._ioContext->get_executor(),[&]{entered.count_down();release.wait();});
  entered.wait();
  for(int i=0;i<100;++i)boost::asio::post(pool._ioContext->get_executor(),[&]{
    // Worker lookups must not race with destruction of any connection.
    assert(pool.GetAsyncConnectionForCurrentThread());
    ++rows;
  });
  auto future=boost::asio::post(pool._ioContext->get_executor(),boost::asio::use_future([]{return 42;}));
  std::thread close([&]{pool.Close();});
  auto limit=std::chrono::steady_clock::now()+std::chrono::seconds(5);
  while(!joining && std::chrono::steady_clock::now()<limit)std::this_thread::yield();
  assert(joining);release.count_down();close.join();
  assert(rows==100 && "shutdown dropped queued SQL operations");
  assert(future.get()==42);
  pool.Close(); // partial initialization/repeated close remains safe
 }
}
"""
checks=checks.replace('INIT_WORK','pool._asyncWork=std::make_unique<DatabaseWorkerPool<MySQLConnection>::AsyncWork>(*pool._ioContext);' if fixed else '')
with tempfile.TemporaryDirectory(prefix='loa-db-shutdown-') as d:
    cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(prefix+checks)
    subprocess.run([compiler,'-std=c++20','-pthread','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'src/common/Asio'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=30)
print('Database shutdown drains queued writes/futures with 1 and 4 real Asio workers')
